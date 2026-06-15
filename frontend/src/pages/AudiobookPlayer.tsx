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
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const loadedBookRef = useRef("");
  const loadedChapterRef = useRef(-1);

  useEffect(() => {
    localStorage.setItem("audiobook-show-video", String(showVideo));
  }, [showVideo]);

  const loadChapter = useCallback(async (chapter: Chapter) => {
    if (chapter.idx === loadedChapterRef.current) return;
    loadedChapterRef.current = chapter.idx;
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

  const loadBook = useCallback(async (key: string) => {
    if (!key) return;
    setLoading(true);
    setError("");
    setManifest(null);
    setChapters([]);
    setCurrentIdx(0);
    try {
      const list = await api.getChapters({ bookKey: key });
      setChapters(list);
      if (list.length > 0) {
        await loadChapter(list[0]);
      } else {
        setError("没有章节");
      }
    } catch (e: unknown) {
      setError(`加载失败: ${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setLoading(false);
    }
  }, [loadChapter]);

  useEffect(() => {
    if (!bookKey || bookKey === loadedBookRef.current) return;
    loadedBookRef.current = bookKey;
    loadedChapterRef.current = -1;
    loadBook(bookKey);
  }, [bookKey, loadBook]);

  const handleChapterChange = useCallback((chapter: Chapter) => {
    const media = mediaRef.current;
    if (media) {
      media.pause();
      media.currentTime = 0;
    }
    loadedChapterRef.current = -1;
    loadChapter(chapter);
  }, [loadChapter]);

  const handleRetry = useCallback(() => {
    loadedChapterRef.current = -1;
    loadedBookRef.current = "";
    loadBook(bookKey);
  }, [bookKey, loadBook]);

  const hasVideo = manifest?.media_files.some((f) => f.media_type === "video") ?? false;
  const currentMedia = manifest?.media_files[0];
  const chapter = chapters.find((ch) => ch.idx === currentIdx);

  if (!bookKey) {
    return <div className="pt-12 text-center text-[13px] text-[#c7c7cc]">缺少 book_key</div>;
  }

  const gradientStyle = {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
  };

  return (
    <div className="min-h-screen" style={gradientStyle}>
      <div className="fixed top-0 inset-x-0 z-50 flex items-center px-4 py-3 bg-white/90 backdrop-blur-xl border-b border-black/[0.06]">
        <button onClick={() => navigate(-1)} className="text-[13px] text-[#86868b] mr-4">
          ← 返回
        </button>
        <span className="text-[14px] font-medium text-[#1d1d1f] truncate flex-1">{bookName}</span>
      </div>

      <div className="pt-14 pb-32">
        {currentMedia && (
          currentMedia.media_type === "video" ? (
            <video
              ref={mediaRef as React.RefObject<HTMLVideoElement>}
              src={currentMedia.url}
              className={`w-full object-contain ${showVideo ? "aspect-video" : "hidden"}`}
              controls={false}
              playsInline
              onError={() => setError("媒体文件加载失败")}
            />
          ) : (
            <audio
              ref={mediaRef as React.RefObject<HTMLAudioElement>}
              src={currentMedia.url}
              onError={() => setError("媒体文件加载失败")}
            />
          )
        )}

        {!showVideo && (
          <div className="flex flex-col items-center justify-center py-8">
            <div className="w-48 h-48 bg-white/20 rounded-2xl backdrop-blur-sm border border-white/30 flex items-center justify-center mb-6">
              {loading ? (
                <p className="text-[13px] text-white/80">加载中...</p>
              ) : (
                <span className={`text-6xl ${currentMedia ? "" : "opacity-20"}`}>🎧</span>
              )}
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">
              {chapter?.title || "加载中..."}
            </h2>
            <p className="text-sm text-white/80">
              {chapters.length > 0 ? `第 ${currentIdx + 1} / ${chapters.length} 章` : ""}
            </p>
          </div>
        )}
        {showVideo && !currentMedia && (
          <div className="mx-auto aspect-video bg-black/5 flex items-center justify-center">
            <span className="text-[80px] opacity-20">🎧</span>
          </div>
        )}

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
