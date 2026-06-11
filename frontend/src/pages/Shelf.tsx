import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, BatchResultItem, BookCategoryItem, BookItem, Chapter, OfflineTaskItem } from "@/api/client";
import {
  cacheChaptersBulk,
  getCachedChapter,
} from "@/utils/chapter-cache";
import { getClientIdentity } from "@/utils/client-identity";
import { loadBooksCache, saveBooksCache, saveChaptersCache } from "@/utils/local-cache";

type OfflineProgressState = {
  completedBooks: number;
  totalBooks: number;
  bookName: string;
  phase: "server" | "browser";
  chapterCurrent: number;
  chapterTotal: number;
};

const OFFLINE_CHAPTER_BATCH_SIZE = 6;

function sortCategoryNames(names: string[]): string[] {
  return Array.from(
    new Set(names.map((name) => name.trim()).filter(Boolean)),
  ).sort((a, b) => {
    if (a === "网文") return -1;
    if (b === "网文") return 1;
    if (a === "出版") return -1;
    if (b === "出版") return 1;
    return a.localeCompare(b, "zh-Hans-CN");
  });
}

export default function Shelf() {
  const [books, setBooks] = useState<BookItem[]>(() => loadBooksCache<BookItem>());
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [editableCategories, setEditableCategories] = useState<string[]>(["网文", "出版"]);
  const [categorySavingId, setCategorySavingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [batchResults, setBatchResults] = useState<BatchResultItem[]>([]);
  const [lastOpType, setLastOpType] = useState<"export" | "cache" | "offline" | "delete" | null>(null);
  const [resultFilter, setResultFilter] = useState<"all" | "success" | "fail">("all");
  const [exportFormat, setExportFormat] = useState<"txt" | "epub">("txt");
  const [cacheProgress, setCacheProgress] = useState<{ current: number; total: number; bookName: string } | null>(null);
  const [offlineProgress, setOfflineProgress] = useState<OfflineProgressState | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const categoryCountMap = useMemo(() => {
    const categoryCount = new Map<string, number>();
    for (const book of books) {
      const name = (book.category_name || "网文").trim() || "网文";
      categoryCount.set(name, (categoryCount.get(name) || 0) + 1);
    }

    return categoryCount;
  }, [books]);

  const filterCategories = useMemo(() => {
    const preferred = ["网文", "出版"];
    const existingNames = sortCategoryNames(Array.from(categoryCountMap.keys()));
    const orderedNames = [
      ...preferred,
      ...existingNames.filter((name) => !preferred.includes(name)),
    ];

    return orderedNames.map((name) => ({
      name,
      count: categoryCountMap.get(name) || 0,
    }));
  }, [categoryCountMap]);

  const filteredBooks = useMemo(() => {
    if (categoryFilter === "all") {
      return books;
    }
    return books.filter((book) => (book.category_name || "网文") === categoryFilter);
  }, [books, categoryFilter]);

  const allSelected = filteredBooks.length > 0 && filteredBooks.every((book) => selectedIds.includes(book.id));

  useEffect(() => {
    const visibleIds = new Set(filteredBooks.map((book) => book.id));
    setSelectedIds((prev) => prev.filter((id) => visibleIds.has(id)));
  }, [filteredBooks]);

  const loadBooks = async () => {
    setLoading(true);
    try {
      const [bookData, categoryData] = await Promise.all([
        api.getBooks(),
        api.getBookCategories(),
      ]);

      setBooks(bookData);
      saveBooksCache(bookData);
      setSelectedIds((prev) => prev.filter((id) => bookData.some((item) => item.id === id)));

      const visibleCategoryNames = (categoryData as BookCategoryItem[])
        .filter((item) => !item.hidden)
        .map((item) => item.name);
      const fallbackCategoryNames = bookData.map((book) => book.category_name || "网文");
      setEditableCategories(
        sortCategoryNames(
          visibleCategoryNames.length > 0 ? visibleCategoryNames : fallbackCategoryNames,
        ),
      );
    } catch {
      // Network failed — keep whatever is already in state (may be from cache)
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBooks().catch(() => {});
  }, []);

  const handleClick = async (book: BookItem) => {
    try {
      const identity = getClientIdentity();
      const syncData = await api.pullSyncProgress(identity.userId, 0, 200);
      const syncProgress = syncData.items.find((item) => item.book_key === book.book_key);
      if (syncProgress && syncProgress.chapter_url) {
        navigate(
          `/read?url=${encodeURIComponent(syncProgress.chapter_url)}&source_url=${encodeURIComponent(syncProgress.source_url)}&title=${encodeURIComponent(syncProgress.chapter_title)}&idx=${syncProgress.chapter_idx}&book_key=${encodeURIComponent(syncProgress.book_key)}&book_url=${encodeURIComponent(book.book_url)}&book_name=${encodeURIComponent(book.name)}&scroll=${syncProgress.position || 0}`
        );
        return;
      }
    } catch {}
    navigate(`/book?book_url=${encodeURIComponent(book.book_url)}&source_url=${encodeURIComponent(book.source_url)}&book_key=${encodeURIComponent(book.book_key)}`);
  };

  const toggleSelected = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds([]);
      return;
    }
    setSelectedIds(filteredBooks.map((book) => book.id));
  };

  const handleChangeCategory = async (book: BookItem, nextCategory: string) => {
    const currentCategory = book.category_name || "网文";
    if (!nextCategory || nextCategory === currentCategory) {
      return;
    }

    setCategorySavingId(book.id);
    try {
      await api.setBookCategory(book.id, nextCategory);
      setBooks((prev) => {
        const next = prev.map((item) =>
          item.id === book.id ? { ...item, category_name: nextCategory } : item,
        );
        saveBooksCache(next);
        return next;
      });
      setStatus(`《${book.name}》已移动到 ${nextCategory}`);
    } catch {
      setStatus(`《${book.name}》分类修改失败`);
    } finally {
      setCategorySavingId(null);
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setBusy(true);
    setStatus("导入中...");
    try {
      const result = await api.importBooks(file);
      setBatchResults([]);
      setStatus(`导入成功: ${file.name}`);
      if (result.failed) {
        setStatus(`导入完成: 成功 ${result.imported || 0}, 失败 ${result.failed}`);
      }
      await loadBooks();
    } catch {
      setStatus("导入失败");
    } finally {
      setBusy(false);
    }
  };

  const runBatch = async (
    action: () => Promise<{ success?: number; deleted?: number; results?: BatchResultItem[] }>,
    successMessage: string,
    opType: "export" | "cache" | "delete",
  ) => {
    if (selectedIds.length === 0) {
      setStatus("请先选择书籍");
      return;
    }
    setBusy(true);
    setResultFilter("all");
    setLastOpType(opType);
    try {
      const result = await action();
      if (result.results) {
        setBatchResults(result.results);
        const failed = result.results.filter((item) => !item.ok);
        if (failed.length > 0) {
          setStatus(`${successMessage}，失败 ${failed.length} 本`);
        } else {
          setStatus(`${successMessage}，共 ${result.results.length} 本`);
        }
      } else {
        setBatchResults([]);
        setStatus(successMessage);
      }
      await loadBooks();
    } catch {
      setStatus("操作失败");
    } finally {
      setBusy(false);
    }
  };

  const handleBatchDelete = async () => {
    await runBatch(
      async () => {
        const result = await api.deleteBooksBatch(selectedIds);
        return {
          ...result,
          results: selectedIds.map((bookId) => ({
            book_id: bookId,
            ok: true,
          })),
        };
      },
      "删除完成",
      "delete",
    );
    setSelectedIds([]);
  };

  const handleBatchCache = async () => {
    const targetBooks = selectedIds.length > 0
      ? filteredBooks.filter((book) => selectedIds.includes(book.id))
      : filteredBooks;
    const targetIds = targetBooks.map((book) => book.id);
    const isAll = selectedIds.length === 0;

    if (targetIds.length === 0) {
      setStatus("当前分类没有可缓存的书籍");
      return;
    }

    setBusy(true);
    setResultFilter("all");
    setLastOpType("cache");
    setBatchResults([]);
    setCacheProgress({ current: 0, total: targetIds.length, bookName: "" });
    setStatus(isAll ? `开始服务器缓存 ${targetIds.length} 本书籍...` : `开始服务器缓存选中 ${targetIds.length} 本书籍...`);

    const accumulated: BatchResultItem[] = [];
    let successCount = 0;

    for (let i = 0; i < targetIds.length; i++) {
      const bookId = targetIds[i];
      const bookName = targetBooks[i]?.name ?? `书籍#${bookId}`;
      setCacheProgress({ current: i + 1, total: targetIds.length, bookName });
      setStatus(`正在服务器缓存 (${i + 1}/${targetIds.length}): ${bookName}`);

      try {
        const res = await api.cacheBooksBatch([bookId]);
        const item = res.results[0] ?? { book_id: bookId, ok: false, error: "无返回" };
        const enriched = { ...item, name: bookName };
        accumulated.push(enriched);
        setBatchResults([...accumulated]);
        if (item.ok) successCount++;
      } catch {
        const failed = { book_id: bookId, ok: false, error: "请求失败", name: bookName };
        accumulated.push(failed);
        setBatchResults([...accumulated]);
      }
    }

    setCacheProgress(null);
    const failed = accumulated.filter((r) => !r.ok).length;
    const scope = isAll ? "当前分类书籍" : "选中书籍";
    if (failed > 0) {
      setStatus(`${scope}服务器缓存完成：成功 ${successCount}，失败 ${failed}`);
    } else {
      setStatus(`${scope}服务器缓存完成：共 ${successCount} 本`);
    }
    await loadBooks();
    setBusy(false);
  };

  const handleBatchExport = async () => {
    await runBatch(
      async () => {
        const result = await api.exportBooksBatch(selectedIds, exportFormat);
        const okFiles = result.results.filter((item) => item.ok && item.download_url);
        for (const file of okFiles) {
          window.open(file.download_url, "_blank");
        }
        return result;
      },
      `批量导出 ${exportFormat.toUpperCase()} 完成`,
      "export",
    );
  };

  const hydrateBrowserOfflineCache = async (
    book: BookItem,
    onProgress?: (progress: { current: number; total: number }) => void,
  ): Promise<{ total: number; cached: number }> => {
    const chapters = await api.getChapters(book.book_key);
    saveChaptersCache(book.book_url, chapters);
    const total = chapters.length;
    onProgress?.({ current: 0, total });

    let cached = 0;
    let processed = 0;

    for (let offset = 0; offset < chapters.length; offset += OFFLINE_CHAPTER_BATCH_SIZE) {
      const batch = chapters.slice(offset, offset + OFFLINE_CHAPTER_BATCH_SIZE) as Chapter[];
      const cachedEntries = await Promise.all(
        batch.map(async (chapter) => {
          if (!chapter.url) {
            return null;
          }

          const existing = await getCachedChapter(chapter.url).catch(() => undefined);
          if (existing !== undefined) {
            return {
              chapterUrl: chapter.url,
              content: existing,
              chapterIdx: chapter.idx,
            };
          }

          try {
            const content = await api.getChapterContent(chapter.url, book.source_url);
            if (content.type === "novel") {
              return {
                chapterUrl: chapter.url,
                content: content.content,
                chapterIdx: chapter.idx,
              };
            }
          } catch {
            // Keep going to maximize usable local chapters.
          }

          return null;
        }),
      );

      const validEntries = cachedEntries.filter(
        (entry): entry is { chapterUrl: string; content: string; chapterIdx: number } => entry !== null,
      );

      if (validEntries.length > 0) {
        await cacheChaptersBulk(book.book_url, validEntries);
        cached += validEntries.length;
      }

      processed += batch.length;
      onProgress?.({ current: Math.min(processed, total), total });
    }

    return { total, cached };
  };

  const waitForOfflineTaskTerminal = async (
    taskId: string,
    onPending?: (task: OfflineTaskItem) => void,
  ): Promise<OfflineTaskItem> => {
    const startedAt = Date.now();
    const timeoutMs = 180000;
    const pollIntervalMs = 500;

    let latest = await api.getOfflineTask(taskId);
    while (latest.status === "queued" || latest.status === "running") {
      onPending?.(latest);
      if (Date.now() - startedAt > timeoutMs) {
        throw new Error("服务器离线任务等待超时");
      }
      await new Promise((resolve) => window.setTimeout(resolve, pollIntervalMs));
      latest = await api.getOfflineTask(taskId);
    }

    return latest;
  };

  const handleBatchOfflineDownload = async () => {
    const targetBooks = selectedIds.length > 0
      ? filteredBooks.filter((book) => selectedIds.includes(book.id))
      : filteredBooks;
    const targetIds = targetBooks.map((book) => book.id);
    const isAll = selectedIds.length === 0;
    if (targetIds.length === 0) {
      setStatus("当前分类没有可进行浏览器缓存的书籍");
      return;
    }

    const identity = getClientIdentity();
    setBusy(true);
    setResultFilter("all");
    setLastOpType("offline");
    setBatchResults([]);
    setOfflineProgress({
      completedBooks: 0,
      totalBooks: targetIds.length,
      bookName: "",
      phase: "server",
      chapterCurrent: 0,
      chapterTotal: 0,
    });
    setStatus(isAll ? `开始浏览器缓存 ${targetIds.length} 本书籍...` : `开始浏览器缓存选中 ${targetIds.length} 本书籍...`);

    const accumulated: BatchResultItem[] = [];
    let successCount = 0;

    for (let i = 0; i < targetIds.length; i++) {
      const bookId = targetIds[i];
      const targetBook = targetBooks[i];
      const bookName = targetBook?.name ?? `书籍#${bookId}`;
      setOfflineProgress({
        completedBooks: i,
        totalBooks: targetIds.length,
        bookName,
        phase: "server",
        chapterCurrent: 0,
        chapterTotal: 0,
      });
      setStatus(`正在服务器缓存 (${i + 1}/${targetIds.length}): ${bookName}`);

      try {
        const createdTask = await api.createOfflineTask({
          user_id: identity.userId,
          device_id: identity.deviceId,
          book_id: bookId,
        });
        const task =
          createdTask.status === "queued" || createdTask.status === "running"
            ? await waitForOfflineTaskTerminal(createdTask.task_id, (pending) => {
                setStatus(
                  `正在服务器缓存 (${i + 1}/${targetIds.length}): ${bookName} ${Math.max(0, Math.min(100, pending.progress || 0))}%`
                );
              })
            : createdTask;
        let ok = task.status === "completed";
        let cachedChapters = task.cached_chapters;
        let totalChapters = task.total_chapters;
        let errorMessage = task.error_message || undefined;

        if (ok && targetBook) {
          setStatus(`正在写入浏览器缓存 (${i + 1}/${targetIds.length}): ${bookName}`);
          const hydrated = await hydrateBrowserOfflineCache(targetBook, ({ current, total }) => {
            setOfflineProgress({
              completedBooks: i,
              totalBooks: targetIds.length,
              bookName,
              phase: "browser",
              chapterCurrent: current,
              chapterTotal: total,
            });
          });
          cachedChapters = hydrated.cached;
          totalChapters = hydrated.total;
          if (hydrated.total > 0 && hydrated.cached === 0) {
            ok = false;
            errorMessage = "浏览器离线缓存失败";
          } else if (hydrated.cached < hydrated.total) {
            errorMessage = `本地缓存不完整 ${hydrated.cached}/${hydrated.total}`;
          } else {
            errorMessage = undefined;
          }
        }

        if (ok) successCount += 1;
        accumulated.push({
          book_id: bookId,
          ok,
          name: bookName,
          cached: cachedChapters,
          total: totalChapters,
          error: ok ? errorMessage : (errorMessage || "浏览器缓存失败"),
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "";
        accumulated.push({
          book_id: bookId,
          ok: false,
          name: bookName,
          error: message || "浏览器缓存请求失败",
        });
      }

      setBatchResults([...accumulated]);
      setOfflineProgress({
        completedBooks: i + 1,
        totalBooks: targetIds.length,
        bookName,
        phase: "server",
        chapterCurrent: 0,
        chapterTotal: 0,
      });
    }

    const failed = accumulated.filter((item) => !item.ok).length;
    const scope = isAll ? "当前分类书籍" : "选中书籍";
    setStatus(
      failed > 0
        ? `${scope}浏览器缓存完成：成功 ${successCount}，失败 ${failed}`
        : `${scope}浏览器缓存完成：共 ${successCount} 本`
    );
    setOfflineProgress(null);
    setBusy(false);
  };

  if (loading) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wider">书架</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate("/offline-catalog")}
            className="px-2.5 py-1.5 rounded-lg bg-[#0a66c2]/10 text-[12px] text-[#0a66c2]"
          >
            离线目录
          </button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".json,.txt,.epub"
        className="hidden"
        onChange={handleImportFile}
      />

      {cacheProgress && (
        <div className="mb-3 p-3 rounded-xl bg-[#c45d35]/[0.06] border border-[#c45d35]/20">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[12px] font-medium text-[#c45d35]">
              正在服务器缓存 {cacheProgress.current}/{cacheProgress.total}
            </span>
            <span className="text-[11px] text-[#86868b]">
              {Math.round((cacheProgress.current / cacheProgress.total) * 100)}%
            </span>
          </div>
          <div className="h-[3px] bg-black/[0.06] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#c45d35] rounded-full transition-all duration-500"
              style={{ width: `${(cacheProgress.current / cacheProgress.total) * 100}%` }}
            />
          </div>
          {cacheProgress.bookName && (
            <p className="text-[11px] text-[#86868b] mt-1.5 truncate">
              {cacheProgress.bookName}
            </p>
          )}
        </div>
      )}

      {offlineProgress && (
        <div className="mb-3 p-3 rounded-xl bg-[#0a66c2]/[0.06] border border-[#0a66c2]/20">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[12px] font-medium text-[#0a66c2]">
              正在浏览器缓存 {offlineProgress.completedBooks}/{offlineProgress.totalBooks}
            </span>
            <span className="text-[11px] text-[#86868b]">
              {offlineProgress.totalBooks > 0
                ? Math.round((offlineProgress.completedBooks / offlineProgress.totalBooks) * 100)
                : 0}%
            </span>
          </div>
          <div className="h-[3px] bg-black/[0.06] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#0a66c2] rounded-full transition-all duration-500"
              style={{
                width: `${offlineProgress.totalBooks > 0
                  ? (offlineProgress.completedBooks / offlineProgress.totalBooks) * 100
                  : 0}%`,
              }}
            />
          </div>
          {offlineProgress.bookName && (
            <p className="text-[11px] text-[#86868b] mt-1.5 truncate">
              {offlineProgress.phase === "browser"
                ? `浏览器缓存 ${offlineProgress.chapterCurrent}/${offlineProgress.chapterTotal} 章 · ${offlineProgress.bookName}`
                : `服务器缓存中（准备浏览器缓存）· ${offlineProgress.bookName}`}
            </p>
          )}
          {offlineProgress.phase === "browser" && offlineProgress.chapterTotal > 0 && (
            <div className="mt-1.5 h-[3px] bg-[#0a66c2]/20 rounded-full overflow-hidden">
              <div
                className="h-full bg-[#0a66c2] rounded-full transition-all duration-200"
                style={{ width: `${(offlineProgress.chapterCurrent / offlineProgress.chapterTotal) * 100}%` }}
              />
            </div>
          )}
        </div>
      )}

      <section className="mb-3 p-3 rounded-xl bg-black/[0.03] border border-black/[0.04]">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setCategoryFilter("all")}
              className={`px-2.5 py-1.5 rounded-lg text-[12px] transition-colors ${
                categoryFilter === "all"
                  ? "bg-[#1d1d1f] text-white"
                  : "bg-black/[0.06] text-[#86868b] hover:text-[#1d1d1f]"
              }`}
            >
              全部 ({books.length})
            </button>
            {filterCategories.map((category) => (
              <button
                key={category.name}
                onClick={() => setCategoryFilter(category.name)}
                className={`px-2.5 py-1.5 rounded-lg text-[12px] transition-colors ${
                  categoryFilter === category.name
                    ? "bg-[#1d1d1f] text-white"
                    : "bg-black/[0.06] text-[#86868b] hover:text-[#1d1d1f]"
                }`}
              >
                {category.name} ({category.count})
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              onClick={toggleSelectAll}
              disabled={filteredBooks.length === 0}
              className={`px-2.5 py-1.5 rounded-lg text-[12px] transition-colors ${
                allSelected
                  ? "bg-[#1d1d1f] text-white"
                  : "bg-black/[0.06] text-[#86868b] hover:text-[#1d1d1f]"
              } disabled:opacity-50`}
            >
              {allSelected ? "取消全选" : "全选"}
            </button>
            <button
              onClick={handleImportClick}
              disabled={busy}
              className="px-2.5 py-1.5 rounded-lg bg-black/[0.06] text-[12px] text-[#86868b] hover:text-[#1d1d1f] disabled:opacity-50"
            >
              导入书籍
            </button>
            <button
              onClick={handleBatchDelete}
              disabled={busy || selectedIds.length === 0}
              className="px-2.5 py-1.5 rounded-lg bg-black/[0.06] text-[12px] text-[#1d1d1f] disabled:opacity-50"
            >
              删除
            </button>
            <button
              onClick={handleBatchCache}
              disabled={busy || filteredBooks.length === 0}
              className="px-2.5 py-1.5 rounded-lg bg-black/[0.06] text-[12px] text-[#1d1d1f] disabled:opacity-50"
            >
              {selectedIds.length > 0 ? `服务器缓存 (${selectedIds.length})` : "服务器缓存"}
            </button>
            <button
              onClick={handleBatchOfflineDownload}
              disabled={busy || filteredBooks.length === 0}
              className="px-2.5 py-1.5 rounded-lg bg-[#0a66c2]/10 text-[12px] text-[#0a66c2] disabled:opacity-50"
            >
              {selectedIds.length > 0 ? `浏览器缓存 (${selectedIds.length})` : "浏览器缓存"}
            </button>
            <select
              value={exportFormat}
              onChange={(event) => setExportFormat(event.target.value as "txt" | "epub")}
              className="px-2.5 py-1.5 rounded-lg bg-black/[0.04] text-[12px] text-[#1d1d1f]"
            >
              <option value="txt">TXT</option>
              <option value="epub">EPUB</option>
            </select>
            <button
              onClick={handleBatchExport}
              disabled={busy || selectedIds.length === 0}
              className="px-2.5 py-1.5 rounded-lg bg-black/[0.06] text-[12px] text-[#1d1d1f] disabled:opacity-50"
            >
              导出 {exportFormat.toUpperCase()}
            </button>
          </div>
        </div>
      </section>

      {status && <p className="text-[12px] text-[#86868b] mb-3">{status}</p>}

      {batchResults.length > 0 && (
        <section className="mb-3 p-3 rounded-xl bg-black/[0.03] border border-black/[0.04]">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[12px] text-[#86868b]">
              {lastOpType === "export" && "导出结果"}
              {lastOpType === "cache" && "服务器缓存结果"}
              {lastOpType === "offline" && "浏览器缓存结果"}
              {lastOpType === "delete" && "删除结果"}
              {!lastOpType && "批量结果"}
              <span className="ml-1 text-[#c7c7cc]">
                ({batchResults.filter((r) => r.ok).length}/{batchResults.length} 成功)
              </span>
            </p>
            <div className="flex gap-1">
              {(["all", "success", "fail"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setResultFilter(f)}
                  className={`px-2 py-0.5 rounded text-[11px] transition-colors ${
                    resultFilter === f
                      ? "bg-[#1d1d1f] text-white"
                      : "bg-black/[0.06] text-[#86868b] hover:text-[#1d1d1f]"
                  }`}
                >
                  {f === "all" ? "全部" : f === "success" ? "成功" : "失败"}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            {batchResults
              .filter((item) =>
                resultFilter === "all"
                  ? true
                  : resultFilter === "success"
                  ? item.ok
                  : !item.ok,
              )
              .map((item) => (
                <div key={`${item.book_id}-${item.file_name || "no-file"}`} className="flex items-center gap-2 text-[12px]">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    item.ok ? "bg-[#2d7d46]" : "bg-[#b42318]"
                  }`} />
                  <span className={item.ok ? "text-[#1d1d1f]" : "text-[#b42318]"}>
                    {item.name ?? `书籍#${item.book_id}`}
                  </span>
                  {item.ok && (lastOpType === "cache" || lastOpType === "offline") && item.cached !== undefined && (
                    <span className="text-[#86868b]">已缓存 {item.cached}/{item.total} 章</span>
                  )}
                  {item.error && <span className="text-[#86868b] truncate">{item.error}</span>}
                  {item.download_url && (
                    <a
                      href={item.download_url}
                      target="_blank"
                      rel="noreferrer"
                      className="ml-auto flex-shrink-0 text-[#0a66c2] underline"
                    >
                      下载
                    </a>
                  )}
                </div>
              ))}
            {batchResults.filter((item) =>
              resultFilter === "all" ? false : resultFilter === "success" ? !item.ok : item.ok,
            ).length === batchResults.length && (
              <p className="text-[11px] text-[#c7c7cc] text-center py-1">无符合条件的结果</p>
            )}
          </div>
        </section>
      )}

      {filteredBooks.length === 0 ? (
        <div className="pt-16 text-center">
          <p className="text-[15px] text-[#86868b]">
            {books.length === 0 ? "书架暂无可见书籍" : "当前分类暂无可见书籍"}
          </p>
          <p className="text-[12px] text-[#c7c7cc] mt-1.5">
            {books.length === 0 ? "从排行榜或搜索结果中添加" : "切换分类或前往设置检查分类可见性"}
          </p>
          <button
            onClick={handleImportClick}
            className="mt-4 px-3 py-2 rounded-lg bg-black/[0.05] text-[12px] text-[#1d1d1f]"
          >
            导入书籍（JSON/TXT/EPUB）
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 md:gap-3">
          {filteredBooks.map((book) => {
            const currentCategory = book.category_name || "网文";
            const categoryOptions = editableCategories.includes(currentCategory)
              ? editableCategories
              : sortCategoryNames([...editableCategories, currentCategory]);

            return (
              <div
                key={book.id}
                className="w-full p-3.5 md:rounded-xl md:bg-white md:shadow-[0_1px_3px_rgba(0,0,0,0.06)] border-b border-black/[0.04] md:border-0"
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(book.id)}
                    onChange={() => toggleSelected(book.id)}
                    className="mt-1"
                  />
                  <div className="flex-1">
                    <button
                      onClick={() => handleClick(book)}
                      className="w-full text-left active:scale-[0.98] transition-transform duration-150"
                    >
                      <p className="text-[15px] font-medium text-[#1d1d1f] truncate">{book.name}</p>
                      <p className="text-[12px] text-[#86868b] mt-1">
                        {book.author ? `${book.author} · ` : ""}{book.total_chapters} 章
                      </p>
                    </button>

                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-[11px] text-[#86868b]">分类</span>
                      <select
                        value={currentCategory}
                        onChange={(event) => handleChangeCategory(book, event.target.value)}
                        disabled={busy || categorySavingId === book.id}
                        className="px-2 py-1 rounded bg-black/[0.05] text-[11px] text-[#1d1d1f] disabled:opacity-50"
                      >
                        {categoryOptions.map((categoryName) => (
                          <option key={categoryName} value={categoryName}>
                            {categoryName}
                          </option>
                        ))}
                      </select>
                      {categorySavingId === book.id && (
                        <span className="text-[11px] text-[#86868b]">保存中...</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
