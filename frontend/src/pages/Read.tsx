import { useEffect, useState, useCallback, useRef, type MouseEvent } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, Chapter, ChapterContent, SyncProgressItem, SyncProgressPayload } from "@/api/client";
import { normalizeReaderTheme, type NormalizedReaderTheme, useReaderStore } from "@/stores/readerStore";
import ReaderSettings from "@/components/reader/ReaderSettings";
import MangaScroll from "@/components/reader/MangaScroll";
import MangaPage from "@/components/reader/MangaPage";
import { cacheChapter, getCachedChapter, getCachedChapterByIndex } from "@/utils/chapter-cache";
import { getClientIdentity } from "@/utils/client-identity";
import { loadChaptersCache, saveChaptersCache } from "@/utils/local-cache";
import { enqueueSyncProgress, flushSyncProgressQueue, getSyncProgressQueueSize } from "@/utils/sync-queue";

const AUTO_PAGE_TURN_INTERVAL_MS = {
  slow: 12000,
  medium: 8000,
  fast: 5000,
} as const;

const CONFLICT_RESOLVE_SYNC_SUPPRESS_MS = 5000;

interface LoadedChapter {
  title: string;
  content: string;
  idx: number;
}

interface ProgressConflictPrompt {
  server: SyncProgressItem;
  local: SyncProgressPayload;
}

function formatProgressLabel(position: number): string {
  const percentValue = position <= 1 ? position * 100 : position;
  const normalized = Math.max(0, Math.min(100, percentValue));
  return `${Math.round(normalized)}%`;
}

export default function Read() {
  const [params, setParams] = useSearchParams();
  const chapterUrl = params.get("url") || "";
  const sourceUrl = params.get("source_url") || "";
  const title = params.get("title") || "";
  const bookKey = params.get("book_key") || "";
  const bookUrl = params.get("book_url") || "";
  const bookName = params.get("book_name") || "";
  const startIdx = parseInt(params.get("idx") || "0");
  const savedScrollPercent = parseFloat(params.get("scroll") || "0");
  const navigate = useNavigate();

  const { settings } = useReaderStore();
  const [showToolbar, setShowToolbar] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showToc, setShowToc] = useState(false);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loadedChapters, setLoadedChapters] = useState<LoadedChapter[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [retryNonce, setRetryNonce] = useState(0);
  const [currentViewIdx, setCurrentViewIdx] = useState(startIdx);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const chapterRefs = useRef<Map<number, HTMLElement>>(new Map());
  const tocRef = useRef<HTMLDivElement>(null);
  const [mangaImages, setMangaImages] = useState<string[]>([]);
  const [contentType, setContentType] = useState<"novel" | "manga">("novel");
  const [mangaMode, setMangaMode] = useState<"scroll" | "page">("scroll");
  const [progressConflict, setProgressConflict] = useState<ProgressConflictPrompt | null>(null);
  const [autoPageTurnEnabled, setAutoPageTurnEnabled] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const scrollSaveRef = useRef<ReturnType<typeof setTimeout>>();
  const autoPageTurnTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const suppressProgressPersistUntilRef = useRef(0);

  const readCachedChapter = useCallback(async (targetUrl: string, targetIdx: number) => {
    const byUrl = await getCachedChapter(targetUrl).catch(() => undefined);
    if (byUrl !== undefined) {
      return byUrl;
    }
    if (!bookUrl) {
      return undefined;
    }
    return getCachedChapterByIndex(bookUrl, targetIdx).catch(() => undefined);
  }, [bookUrl]);

  // Load chapter list
  useEffect(() => {
    if (!bookUrl || !sourceUrl) return;
    api.getChapters({ bookKey, bookUrl, sourceUrl })
      .then((list) => { saveChaptersCache(bookUrl, list); setChapters(list); })
      .catch(() => {
        const cached = loadChaptersCache<Chapter>(bookUrl);
        if (cached.length > 0) setChapters(cached);
      });
  }, [bookKey, bookUrl, sourceUrl]);

  // Load initial chapter with IndexedDB cache
  useEffect(() => {
    if (!chapterUrl || !sourceUrl) return;

    setLoading(true);
    setLoadError("");
    setLoadedChapters([]);

    const restoreScroll = () => {
      if (savedScrollPercent > 0) {
        requestAnimationFrame(() => {
          const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
          window.scrollTo(0, maxScroll * savedScrollPercent);
        });
      } else {
        window.scrollTo(0, 0);
      }
    };

    const handleResponse = (res: ChapterContent) => {
      setLoadError("");
      if (res.type === "manga") {
        setContentType("manga");
        setMangaImages(res.images);
        setLoading(false);
      } else {
        setContentType("novel");
        setMangaImages([]);
        setLoadedChapters([{ title, content: res.content, idx: startIdx }]);
        setCurrentViewIdx(startIdx);
        setLoading(false);
        setTimeout(restoreScroll, 100);
        cacheChapter(bookUrl, chapterUrl, res.content, startIdx).catch(() => {});
        prefetchChapters(startIdx);
      }
    };

    const handleFailure = (cached?: string) => {
      if (!cached) {
        setLoading(false);
        setLoadError(navigator.onLine ? "章节加载失败" : "该章节未离线缓存，请先联网打开或执行离线下载");
      }
    };

    readCachedChapter(chapterUrl, startIdx).then((cached: string | undefined) => {
      if (cached) {
        setContentType("novel");
        setLoadedChapters([{ title, content: cached, idx: startIdx }]);
        setCurrentViewIdx(startIdx);
        setLoading(false);
        setTimeout(restoreScroll, 100);
      }
      api.getChapterContent(chapterUrl, sourceUrl).then((res) => {
        handleResponse(res);
      }).catch(() => handleFailure(cached));
    }).catch(() => {
      api.getChapterContent(chapterUrl, sourceUrl).then(handleResponse).catch(() => handleFailure());
    });
  }, [chapterUrl, sourceUrl, title, startIdx, retryNonce, bookUrl, readCachedChapter]);

  // Auto-load next chapter on scroll to bottom
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !loading) {
          loadNextChapter();
        }
      },
      { threshold: 0.1 }
    );
    if (sentinelRef.current) observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  });

  // Track which chapter is in view — rootMargin targets screen center
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const idx = Number(entry.target.getAttribute("data-chapter-idx"));
            if (!isNaN(idx)) {
              setCurrentViewIdx(idx);
            }
          }
        }
      },
      { threshold: 0, rootMargin: "-20% 0px -70% 0px" }
    );
    chapterRefs.current.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  });

  const buildCurrentProgressPayload = useCallback((): SyncProgressPayload | null => {
    if (Date.now() < suppressProgressPersistUntilRef.current) {
      return null;
    }
    if (!bookUrl || !sourceUrl || !bookKey || chapters.length === 0 || progressConflict) {
      return null;
    }
    const ch = chapters.find((c) => c.idx === currentViewIdx);
    if (!ch) {
      return null;
    }
    const scrollPercent = document.documentElement.scrollHeight > window.innerHeight
      ? window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)
      : 0;
    const position = Math.round(scrollPercent * 1000) / 1000;
    const identity = getClientIdentity();

    return {
      user_id: identity.userId,
      device_id: identity.deviceId,
      book_key: bookKey,
      book_url: bookUrl,
      source_url: sourceUrl,
      book_name: bookName || title,
      chapter_idx: currentViewIdx,
      chapter_title: ch.title,
      chapter_url: ch.url,
      position,
    };
  }, [bookUrl, sourceUrl, bookKey, chapters, currentViewIdx, progressConflict, bookName, title]);

  const syncProgressPayload = useCallback((payload: SyncProgressPayload) => {
    api.upsertSyncProgress(payload).then((res) => {
      if (!res.accepted && res.conflict) {
        if (Date.now() < suppressProgressPersistUntilRef.current) {
          return;
        }
        setProgressConflict({ server: res, local: payload });
        return;
      }
      if (getSyncProgressQueueSize() > 0) {
        flushSyncProgressQueue(async (queued) => {
          const replayResult = await api.upsertSyncProgress(queued);
          if (!replayResult.accepted && replayResult.conflict) {
            throw new Error("sync conflict");
          }
          return replayResult;
        }).catch(() => {});
      }
    }).catch(() => {
      enqueueSyncProgress(payload);
    });
  }, []);

  const persistProgressNow = useCallback(() => {
    const payload = buildCurrentProgressPayload();
    if (!payload) {
      return;
    }
    syncProgressPayload(payload);
  }, [buildCurrentProgressPayload, syncProgressPayload]);

  // Auto-save progress with scroll position (debounced 2s on scroll, immediate on chapter change/exit)
  useEffect(() => {
    if (!bookUrl || !sourceUrl || !bookKey || chapters.length === 0 || progressConflict) return;

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(persistProgressNow, 1200);

    const handleScroll = () => {
      if (scrollSaveRef.current) clearTimeout(scrollSaveRef.current);
      scrollSaveRef.current = setTimeout(persistProgressNow, 2000);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      if (scrollSaveRef.current) clearTimeout(scrollSaveRef.current);
      window.removeEventListener("scroll", handleScroll);
    };
  }, [
    bookUrl,
    sourceUrl,
    bookKey,
    chapters.length,
    currentViewIdx,
    progressConflict,
    persistProgressNow,
  ]);

  useEffect(() => {
    return () => {
      if (autoPageTurnTimerRef.current) clearTimeout(autoPageTurnTimerRef.current);
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      if (scrollSaveRef.current) clearTimeout(scrollSaveRef.current);
      persistProgressNow();
    };
  }, [persistProgressNow]);

  // Prefetch next 3 chapters in background
  const prefetchChapters = useCallback((fromIdx: number) => {
    if (chapters.length === 0) return;
    const prefetchCount = 3;
    (async () => {
      for (let i = 1; i <= prefetchCount; i++) {
        const ch = chapters.find((c) => c.idx === fromIdx + i);
        if (!ch?.url) continue;
        const cached = await readCachedChapter(ch.url, ch.idx).catch(() => null);
        if (cached) continue;
        try {
          const res = await api.getChapterContent(ch.url, sourceUrl);
          if (res.type === "novel") await cacheChapter(bookUrl, ch.url, res.content, ch.idx);
        } catch { break; }
      }
    })();
  }, [chapters, sourceUrl, bookUrl, readCachedChapter]);

  const loadNextChapter = useCallback(() => {
    if (loading || loadedChapters.length === 0 || chapters.length === 0) return;
    const lastLoaded = loadedChapters[loadedChapters.length - 1];
    const nextChapter = chapters.find((ch) => ch.idx === lastLoaded.idx + 1);
    if (!nextChapter || !nextChapter.url) return;

    setLoading(true);
    readCachedChapter(nextChapter.url, nextChapter.idx).then((cached: string | undefined) => {
      if (cached) {
        setLoadedChapters((prev) => [
          ...prev,
          { title: nextChapter.title, content: cached, idx: nextChapter.idx },
        ]);
        setLoading(false);
      }
      api.getChapterContent(nextChapter.url, sourceUrl).then((res) => {
        if (res.type === "novel") {
          if (!cached) {
            setLoadedChapters((prev) => [
              ...prev,
              { title: nextChapter.title, content: res.content, idx: nextChapter.idx },
            ]);
          }
          setLoading(false);
          cacheChapter(bookUrl, nextChapter.url, res.content, nextChapter.idx).catch(() => {});
          prefetchChapters(nextChapter.idx);
        } else {
          setLoading(false);
        }
      }).catch(() => { if (!cached) setLoading(false); });
    }).catch(() => {
      api.getChapterContent(nextChapter.url, sourceUrl).then((res) => {
        if (res.type === "novel") {
          setLoadedChapters((prev) => [
            ...prev,
            { title: nextChapter.title, content: res.content, idx: nextChapter.idx },
          ]);
        }
        setLoading(false);
      }).catch(() => setLoading(false));
    });
  }, [loading, loadedChapters, chapters, sourceUrl, bookUrl, prefetchChapters, readCachedChapter]);

  const goToChapter = useCallback((chapter: Chapter) => {
    persistProgressNow();
    setParams({
      url: chapter.url,
      source_url: sourceUrl,
      title: chapter.title,
      idx: String(chapter.idx),
      book_key: bookKey,
      book_url: bookUrl,
      book_name: bookName,
    });
    setShowToc(false);
    setShowToolbar(false);
    setShowSettings(false);
  }, [persistProgressNow, setParams, sourceUrl, bookKey, bookUrl, bookName]);

  useEffect(() => {
    if (!autoPageTurnEnabled || contentType !== "novel" || showSettings || showToc || loading) {
      if (autoPageTurnTimerRef.current) {
        clearTimeout(autoPageTurnTimerRef.current);
      }
      return;
    }

    const intervalMs = AUTO_PAGE_TURN_INTERVAL_MS[settings.autoPageTurnSpeed];
    autoPageTurnTimerRef.current = setTimeout(() => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      if (maxScroll <= 0) {
        const next = chapters.find((ch) => ch.idx === currentViewIdx + 1);
        if (next) {
          goToChapter(next);
        }
        return;
      }

      const currentScroll = window.scrollY;
      const nearBottom = currentScroll >= maxScroll - 12;
      if (nearBottom) {
        const next = chapters.find((ch) => ch.idx === currentViewIdx + 1);
        if (next) {
          goToChapter(next);
        }
        return;
      }

      const targetScroll = Math.min(currentScroll + window.innerHeight * 0.88, maxScroll);
      window.scrollTo({ top: targetScroll, behavior: "smooth" });
    }, intervalMs);

    return () => {
      if (autoPageTurnTimerRef.current) {
        clearTimeout(autoPageTurnTimerRef.current);
      }
    };
  }, [
    autoPageTurnEnabled,
    contentType,
    showSettings,
    showToc,
    loading,
    chapters,
    currentViewIdx,
    settings.autoPageTurnSpeed,
    goToChapter,
  ]);

  const toggleToolbar = useCallback(() => {
    if (showToc || showSettings) {
      setShowToc(false);
      setShowSettings(false);
      return;
    }
    setShowToolbar((v) => !v);
  }, [showToc, showSettings]);

  const goPrev = () => {
    const prev = chapters.find((ch) => ch.idx === currentViewIdx - 1);
    if (prev) goToChapter(prev);
  };

  const turnPageByTap = useCallback((direction: "prev" | "next") => {
    if (contentType !== "novel" || loading || showSettings || showToc) {
      return;
    }

    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    const currentScroll = window.scrollY;
    const step = window.innerHeight * 0.9;

    if (direction === "next") {
      if (maxScroll <= 0 || currentScroll >= maxScroll - 12) {
        const next = chapters.find((ch) => ch.idx === currentViewIdx + 1);
        if (next) {
          goToChapter(next);
        }
        return;
      }
      const targetScroll = Math.min(currentScroll + step, maxScroll);
      window.scrollTo({ top: targetScroll, behavior: "smooth" });
      return;
    }

    if (currentScroll <= 12) {
      const prev = chapters.find((ch) => ch.idx === currentViewIdx - 1);
      if (prev) {
        goToChapter(prev);
      }
      return;
    }

    const targetScroll = Math.max(0, currentScroll - step);
    window.scrollTo({ top: targetScroll, behavior: "smooth" });
  }, [chapters, contentType, currentViewIdx, goToChapter, loading, showSettings, showToc]);

  const handleReaderTap = useCallback((event: MouseEvent<HTMLDivElement>) => {
    if (showSettings || showToc || progressConflict) {
      return;
    }

    if (contentType !== "novel" || loading) {
      toggleToolbar();
      return;
    }

    const target = event.target as HTMLElement | null;
    if (target?.closest("button,a,input,select,textarea,label,[role='button']")) {
      return;
    }

    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
    if (!viewportWidth) {
      toggleToolbar();
      return;
    }

    if (event.clientX <= viewportWidth * 0.32) {
      turnPageByTap("prev");
      return;
    }

    if (event.clientX >= viewportWidth * 0.68) {
      turnPageByTap("next");
      return;
    }

    toggleToolbar();
  }, [contentType, loading, progressConflict, showSettings, showToc, toggleToolbar, turnPageByTap]);

  const toggleAutoPageTurn = useCallback(() => {
    if (contentType !== "novel" || loading) {
      setAutoPageTurnEnabled(false);
      return;
    }
    setAutoPageTurnEnabled((value) => !value);
  }, [contentType, loading]);

  const applyServerProgressFromConflict = () => {
    if (!progressConflict) return;
    const server = progressConflict.server;
    suppressProgressPersistUntilRef.current = Date.now() + CONFLICT_RESOLVE_SYNC_SUPPRESS_MS;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    if (scrollSaveRef.current) clearTimeout(scrollSaveRef.current);
    setCurrentViewIdx(server.chapter_idx);
    const nextParams: Record<string, string> = {
      url: server.chapter_url,
      source_url: server.source_url,
      title: server.chapter_title,
      idx: String(server.chapter_idx),
      book_key: server.book_key,
      book_url: server.book_url,
      book_name: server.book_name,
      scroll: String(server.position || 0),
    };
    setProgressConflict(null);
    setShowToolbar(false);
    setShowSettings(false);
    setShowToc(false);
    setParams(nextParams, { replace: true });
  };

  const overwriteServerWithLocalProgress = () => {
    if (!progressConflict) return;
    const forcePayload: SyncProgressPayload = {
      ...progressConflict.local,
      force: true,
    };
    api.upsertSyncProgress(forcePayload).then(() => {
      setProgressConflict(null);
      if (getSyncProgressQueueSize() > 0) {
        flushSyncProgressQueue(async (queued) => {
          const replayResult = await api.upsertSyncProgress(queued);
          if (!replayResult.accepted && replayResult.conflict) {
            throw new Error("sync conflict");
          }
          return replayResult;
        }).catch(() => {});
      }
    }).catch(() => {
      enqueueSyncProgress(forcePayload);
      setProgressConflict(null);
    });
  };

  const hasPrev = chapters.some((ch) => ch.idx === currentViewIdx - 1);
  const lastIdx = loadedChapters.length > 0 ? loadedChapters[loadedChapters.length - 1].idx : startIdx;
  const hasNext = chapters.some((ch) => ch.idx === lastIdx + 1);

  // Scroll TOC to current chapter
  useEffect(() => {
    if (showToc && tocRef.current) {
      requestAnimationFrame(() => {
        const active = tocRef.current?.querySelector("[data-active='true']");
        if (active) active.scrollIntoView({ block: "center", behavior: "instant" });
      });
    }
  }, [showToc]);

  const activeTheme = normalizeReaderTheme(settings.theme);
  const isNightTheme = activeTheme === "night";

  const themeStyles: Record<NormalizedReaderTheme, string> = {
    light: "bg-white text-[#1d1d1f]",
    sepia: "bg-[#f8f3eb] text-[#3d3425]",
    mint: "bg-[#edf6ee] text-[#2a3a2d]",
    blue: "bg-[#edf3fb] text-[#23364c]",
    gray: "bg-[#f0f2f5] text-[#2f3238]",
    night: "bg-[#121316] text-[#d8dbe2]",
  };

  const bottomBarTheme: Record<NormalizedReaderTheme, string> = {
    light: "bg-white/95 border-black/[0.06] text-[#1d1d1f]",
    sepia: "bg-[#f8f3eb]/95 border-[#3d3425]/10 text-[#3d3425]",
    mint: "bg-[#edf6ee]/95 border-[#2a3a2d]/15 text-[#2a3a2d]",
    blue: "bg-[#edf3fb]/95 border-[#23364c]/12 text-[#23364c]",
    gray: "bg-[#f0f2f5]/95 border-[#2f3238]/12 text-[#2f3238]",
    night: "bg-[#16171a]/95 border-white/[0.12] text-[#e5e5e7]",
  };

  const readerButtonPressClass = isNightTheme ? "active:bg-white/[0.08]" : "active:bg-black/[0.05]";
  const tocPanelClass = isNightTheme ? "bg-[#17181b] border-r border-white/[0.08]" : "bg-white";
  const tocHeaderClass = isNightTheme ? "border-white/[0.08] bg-[#17181b]" : "border-black/[0.06] bg-white";
  const tocTitleClass = isNightTheme ? "text-[#9ea0a8]" : "text-[#86868b]";
  const tocItemClass = isNightTheme ? "text-[#e5e5e7] hover:bg-white/[0.06]" : "text-[#1d1d1f] hover:bg-black/[0.03]";
  const tocActiveClass = isNightTheme
    ? "text-[#ffd58a] font-medium bg-[#ffd58a]/[0.12]"
    : "text-[#c45d35] font-medium bg-[#c45d35]/[0.04]";
  const retryButtonClass = isNightTheme
    ? "bg-white/[0.10] text-[#e5e5e7] active:bg-white/[0.16]"
    : "bg-black/[0.06] text-[#1d1d1f] active:bg-black/[0.10]";
  const conflictCardClass = isNightTheme
    ? "w-full md:w-[420px] rounded-t-xl md:rounded-xl bg-[#1b1c1f] p-5 shadow-xl border border-white/[0.12]"
    : "w-full md:w-[420px] rounded-t-xl md:rounded-xl bg-white p-5 shadow-xl border border-black/[0.06]";
  const conflictTitleClass = isNightTheme ? "text-[15px] font-semibold text-[#e5e5e7]" : "text-[15px] font-semibold text-[#1d1d1f]";
  const conflictBodyClass = isNightTheme ? "text-[12px] text-[#9ea0a8] mt-2 leading-[1.7]" : "text-[12px] text-[#86868b] mt-2 leading-[1.7]";
  const conflictInfoPanelClass = isNightTheme ? "mt-3 p-3 rounded-lg bg-white/[0.06]" : "mt-3 p-3 rounded-lg bg-black/[0.04]";
  const conflictInfoTitleClass = isNightTheme ? "text-[12px] text-[#e5e5e7] font-medium" : "text-[12px] text-[#1d1d1f] font-medium";
  const conflictInfoMetaClass = isNightTheme ? "text-[12px] text-[#9ea0a8] mt-1" : "text-[12px] text-[#86868b] mt-1";
  const conflictLaterClass = isNightTheme
    ? "mt-2 w-full px-3 py-2 rounded-lg bg-white/[0.06] text-[12px] text-[#9ea0a8]"
    : "mt-2 w-full px-3 py-2 rounded-lg bg-black/[0.04] text-[12px] text-[#86868b]";

  const paddingMap = { sm: "px-4", md: "px-6", lg: "px-10" };

  if (!bookKey) {
    return <div className="pt-12 text-center text-[13px] text-[#c7c7cc]">缺少 book_key</div>;
  }

  return (
    <div
      className={`min-h-screen ${themeStyles[activeTheme]}`}
      onClick={handleReaderTap}
    >
      {/* Top toolbar */}
      {showToolbar && (
        <div
          className="fixed top-0 inset-x-0 z-50 flex items-center px-4 py-3 bg-black/80 text-white backdrop-blur-sm"
          onClick={(e) => e.stopPropagation()}
        >
          <button onClick={() => navigate(-1)} className="text-[13px] mr-4">
            ← 返回
          </button>
          <button onClick={() => navigate("/")} className="text-[13px] mr-4">
            首页
          </button>
          <span className="text-[13px] truncate flex-1">
            {chapters.find((ch) => ch.idx === currentViewIdx)?.title || title}
          </span>
          {contentType === "manga" && (
            <button
              onClick={() => setMangaMode((m) => m === "scroll" ? "page" : "scroll")}
              className="text-[13px] ml-2"
            >
              {mangaMode === "scroll" ? "页模式" : "条模式"}
            </button>
          )}
          <button
            onClick={() => {
              setShowSettings(true);
            }}
            className="text-[13px] ml-2"
          >
            设置
          </button>
        </div>
      )}

      {/* Content */}
      {contentType === "manga" ? (
        <div className="pb-16">
          {mangaMode === "scroll" ? (
            <MangaScroll images={mangaImages} sourceUrl={sourceUrl} />
          ) : (
            <MangaPage images={mangaImages} sourceUrl={sourceUrl} />
          )}
        </div>
      ) : (
        <div
          className={`w-full max-w-[1200px] mx-auto pt-6 pb-24 ${paddingMap[settings.padding]}`}
          style={{
            fontSize: `${settings.fontSize}px`,
            lineHeight: settings.lineHeight,
            fontFamily: "var(--reader-font-family)",
          }}
        >
          {loadedChapters.map((ch) => (
            <section
              key={ch.idx}
              ref={(el) => { if (el) chapterRefs.current.set(ch.idx, el); }}
              data-chapter-idx={ch.idx}
              className="mb-10"
            >
              <h2 className="text-center font-medium mb-8 text-[13px] opacity-40 tracking-wide">
                {ch.title}
              </h2>
              <div className="whitespace-pre-wrap leading-[1.9]">{ch.content}</div>
            </section>
          ))}

          {loading && (
            <p className="text-center opacity-40 py-6 text-[13px]">加载中...</p>
          )}

          {!loading && loadError && loadedChapters.length === 0 && (
            <div className="text-center py-12">
              <p className="opacity-40 text-[13px] mb-3">{loadError}</p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setRetryNonce((v) => v + 1);
                }}
                className={`px-4 py-2 rounded-lg text-[13px] ${retryButtonClass}`}
              >
                重试
              </button>
            </div>
          )}

          {hasNext && !loading && (
            <div ref={sentinelRef} className="h-20" />
          )}

          {!hasNext && loadedChapters.length > 0 && (
            <p className="text-center opacity-30 py-6 text-[13px]">— 已是最新章节 —</p>
          )}
        </div>
      )}

      {/* Bottom nav */}
      <div
        className={`fixed bottom-0 inset-x-0 z-40 flex items-center justify-between px-6 py-3 backdrop-blur-sm border-t ${bottomBarTheme[activeTheme]}`}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={goPrev}
          disabled={!hasPrev}
          className={`text-[13px] px-3 py-2 rounded-lg disabled:opacity-20 ${readerButtonPressClass}`}
        >
          上一章
        </button>
        <button
          onClick={() => {
            setShowToc(true);
            setShowToolbar(false);
          }}
          className={`text-[13px] px-3 py-2 rounded-lg ${readerButtonPressClass}`}
        >
          目录 ({chapters.length})
        </button>
        <button
          onClick={() => {
            const next = chapters.find((ch) => ch.idx === currentViewIdx + 1);
            if (next) goToChapter(next);
          }}
          disabled={!chapters.some((ch) => ch.idx === currentViewIdx + 1)}
          className={`text-[13px] px-3 py-2 rounded-lg disabled:opacity-20 ${readerButtonPressClass}`}
        >
          下一章
        </button>
      </div>

      {/* TOC drawer */}
      {showToc && (
        <div
          className="fixed inset-0 z-50 flex"
          onClick={() => setShowToc(false)}
        >
          <div
            ref={tocRef}
            className={`w-72 max-w-[80vw] h-full shadow-2xl overflow-y-auto ${tocPanelClass}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={`sticky top-0 px-5 py-4 border-b z-10 ${tocHeaderClass}`}>
              <h3 className={`text-[12px] font-semibold uppercase tracking-wider ${tocTitleClass}`}>
                目录 · {chapters.length} 章
              </h3>
            </div>
            <div className="py-1">
              {chapters.map((ch) => (
                <button
                  key={ch.idx}
                  data-active={ch.idx === currentViewIdx ? "true" : undefined}
                  onClick={() => goToChapter(ch)}
                  className={`block w-full text-left px-5 py-2.5 text-[13px] truncate transition-colors ${
                    ch.idx === currentViewIdx
                      ? tocActiveClass
                      : tocItemClass
                  }`}
                >
                  {ch.title}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 bg-black/30" />
        </div>
      )}

      {progressConflict && (
        <div className="fixed inset-0 z-[60] bg-black/60 flex items-end md:items-center justify-center" onClick={(e) => e.stopPropagation()}>
          <div className={conflictCardClass}>
            <h3 className={conflictTitleClass}>检测到跨设备进度冲突</h3>
            <p className={conflictBodyClass}>
              {progressConflict.server.conflict_reason === "chapter_regression" ? "云端章节更靠后" : "云端阅读位置更靠后"}，请选择保留哪一端进度。
            </p>
            <div className={conflictInfoPanelClass}>
              <p className={conflictInfoTitleClass}>云端进度</p>
              <p className={conflictInfoMetaClass}>
                第 {progressConflict.server.chapter_idx + 1} 章 · {formatProgressLabel(progressConflict.server.position)}
              </p>
              <p className={`${conflictInfoTitleClass} mt-2`}>本机进度</p>
              <p className={conflictInfoMetaClass}>
                第 {progressConflict.local.chapter_idx + 1} 章 · {formatProgressLabel(progressConflict.local.position)}
              </p>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                onClick={applyServerProgressFromConflict}
                className="flex-1 px-3 py-2 rounded-lg bg-[#0a66c2]/10 text-[12px] text-[#0a66c2]"
              >
                使用云端进度
              </button>
              <button
                onClick={overwriteServerWithLocalProgress}
                className="flex-1 px-3 py-2 rounded-lg bg-[#c45d35]/10 text-[12px] text-[#c45d35]"
              >
                以本机进度覆盖
              </button>
            </div>
            <button
              onClick={() => setProgressConflict(null)}
              className={conflictLaterClass}
            >
              稍后处理
            </button>
          </div>
        </div>
      )}

      {showSettings && (
        <ReaderSettings
          onClose={() => setShowSettings(false)}
          autoPageTurnEnabled={autoPageTurnEnabled}
          onToggleAutoPageTurn={toggleAutoPageTurn}
        />
      )}
    </div>
  );
}
