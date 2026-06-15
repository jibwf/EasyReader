import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, type Chapter, type AudiobookManifest } from "@/api/client";
import AudiobookControls from "@/components/reader/AudiobookControls";

export default function AudiobookPlayer() {
  const [params] = useSearchParams();
  const bookKey = params.get("book_key") || "";
  const bookName = params.get("book_name") || "";
  const navigate = useNavigate();

  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [manifest, setManifest] = useState<AudiobookManifest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showVideo, setShowVideo] = useState(() => {
    return localStorage.getItem("audiobook-show-video") !== "false";
  });
  const mediaRef = useRef<HTMLVideoElement>(null);
  const loadedBookRef = useRef<string>("");

  useEffect(() => {
    localStorage.setItem("audiobook-show-video", String(showVideo));
  }, [showVideo]);

  useEffect(() => {
    if (!bookKey || bookKey === loadedBookRef.current) return;
    loadedBookRef.current = bookKey;
    setLoading(true);
    setError("");
    setManifest(null);
    api.getChapters({ bookKey })
      .then((list) => {
        setChapters(list);
        if (list.length > 0) {
          loadChapter(list[0]);
        } else {
          setLoading(false);
          setError("没有章节");
        }
      })
      .catch((e: unknown) => {
        setLoading(false);
        setError(`加载章节失败: ${e instanceof Error ? e.message : "未知错误"}`);
      });
  }, [bookKey]);

  const loadChapter = useCallback(async (chapter: Chapter) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.getChapterContent(chapter.url, "local://audiobook");
      if (res.type === "audiobook") {
        setManifest(res.manifest);
        setCurrentIdx(chapter.idx);
      } else {
        setError(`内容类型异常: ${res.type}`);
      }
    } catch (e: unknown) {
      setManifest(null);
      setError(`加载内容失败: ${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChapterChange = useCallback((chapter: Chapter) => {
    if (mediaRef.current) {
      mediaRef.current.pause();
      mediaRef.current.currentTime = 0;
    }
    loadChapter(chapter);
  }, [loadChapter]);

  const handleRetry = useCallback(() => {
    if (chapters.length > 0) {
      loadChapter(chapters[currentIdx] || chapters[0]);
    } else if (bookKey) {
      loadedBookRef.current = "";
      setLoading(true);
      setError("");
      api.getChapters({ bookKey })
        .then((list) => {
          setChapters(list);
          if (list.length > 0) loadChapter(list[0]);
          else setError("没有章节");
        })
        .catch((e: unknown) => setError(`加载失败: ${e instanceof Error ? e.message : "未知错误"}`))
        .finally(() => setLoading(false));
    }
  }, [chapters, currentIdx, bookKey, loadChapter]);

  const hasVideo = manifest?.media_files.some((f) => f.media_type === "video") ?? false;
  const currentMedia = manifest?.media_files[0];
  const chapter = chapters.find((ch) => ch.idx === currentIdx);

  if (!bookKey) {
    return <div className="pt-12 text-center text-[13px] text-[#c7c7cc]">缺少 book_key</div>;
  }

  return (
    <div className="min-h-screen bg-[#fafafa]">
      <div className="fixed top-0 inset-x-0 z-50 flex items-center px-4 py-3 bg-white/90 backdrop-blur-xl border-b border-black/[0.06]">
        <button onClick={() => navigate(-1)} className="text-[13px] text-[#86868b] mr-4">
          ← 返回
        </button>
        <span className="text-[14px] font-medium text-[#1d1d1f] truncate flex-1">{bookName}</span>
      </div>

      <div className="pt-14 pb-32">
        <div className={`mx-auto ${showVideo && hasVideo ? "aspect-video" : "aspect-square max-w-[300px]"} bg-black/5 flex items-center justify-center`}>
          {loading ? (
            <p className="text-[13px] text-[#c7c7cc]">加载中...</p>
          ) : currentMedia ? (
            showVideo && currentMedia.media_type === "video" ? (
              <video
                ref={mediaRef}
                src={currentMedia.url}
                className="w-full h-full object-contain"
                controls={false}
                playsInline
              />
            ) : currentMedia.media_type === "video" ? (
              <video
                ref={mediaRef}
                src={currentMedia.url}
                className="w-full h-full object-contain"
                controls={false}
                playsInline
                style={{ display: "none" }}
              />
            ) : (
              <>
                <audio ref={mediaRef} src={currentMedia.url} />
                <span className="text-[80px]">🎧</span>
              </>
            )
          ) : (
            <span className="text-[80px] opacity-20">🎧</span>
          )}
        </div>

        <div className="px-4 mt-4 text-center">
          <h2 className="text-[16px] font-medium text-[#1d1d1f]">
            {chapter?.title || "加载中..."}
          </h2>
          <p className="text-[12px] text-[#86868b] mt-1">
            第 {currentIdx + 1} / {chapters.length} 章
          </p>
        </div>

        {error && (
          <div className="mx-4 mt-4 p-3 rounded-lg bg-red-50 border border-red-200">
            <p className="text-[13px] text-red-600">{error}</p>
            <button
              onClick={handleRetry}
              className="mt-2 px-4 py-1.5 rounded-lg bg-red-100 text-[13px] text-red-700 active:bg-red-200"
            >
              重试
            </button>
          </div>
        )}

        {manifest && (
          <div className="mt-6">
            <AudiobookControls
              mediaRef={mediaRef}
              chapters={chapters}
              currentIdx={currentIdx}
              onChapterChange={handleChapterChange}
              showVideo={showVideo}
              onToggleVideo={() => setShowVideo((v) => !v)}
              hasVideo={hasVideo}
            />
          </div>
        )}
      </div>
    </div>
  );
}
