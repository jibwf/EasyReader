import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, type Chapter, type AudiobookManifest } from "@/api/client";
import AudiobookControls from "@/components/reader/AudiobookControls";
import { useAudiobookHistory } from "@/stores/audiobookHistory";
import { useAudiobookOffline } from "@/stores/audiobookOffline";
import { HeadphonesIcon, DownloadIcon, CheckCircleIcon, XCircleIcon } from "@/components/icons";

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

  const { addHistory, getHistory } = useAudiobookHistory();
  const {
    isChapterCached,
    downloadChapter,
    downloadEntireBook,
    cancelDownload,
    downloadProgress,
    getBookCachedChapters
  } = useAudiobookOffline();

  const hasVideo = manifest?.media_files.some((f) => f.media_type === "video") ?? false;
  const currentMedia = manifest?.media_files[0];
  const chapter = chapters.find((ch) => ch.idx === currentIdx);

  // 边听边存：播放时自动缓存当前章节
  useEffect(() => {
    if (!bookKey || chapters.length === 0) return;

    // 缓存当前章节（使用 media URL 而非 chapter URL）
    if (currentMedia && chapter) {
      downloadChapter(bookKey, chapter.idx, chapter.title, currentMedia.url).catch(() => {
        // 忽略错误，不影响播放
      });
    }
  }, [currentIdx, currentMedia, bookKey, chapter, chapters, downloadChapter, isChapterCached]);

  // 检查当前章节是否已缓存
  const isCurrentChapterCached = chapter ? isChapterCached(bookKey, chapter.idx) : false;

  // 获取已缓存的章节数量
  const cachedChaptersCount = getBookCachedChapters(bookKey).length;

  // 下载整本有声书
  const handleDownloadBook = useCallback(async () => {
    if (chapters.length === 0) return;
    
    const chaptersToDownload = chapters.map(ch => ({
      idx: ch.idx,
      title: ch.title,
      url: ch.url
    }));
    
    await downloadEntireBook(bookKey, chaptersToDownload);
  }, [chapters, bookKey, downloadEntireBook]);

  // 取消下载
  const handleCancelDownload = useCallback(() => {
    cancelDownload();
  }, [cancelDownload]);

  // 在加载书籍时恢复播放进度
  useEffect(() => {
    if (bookKey) {
      const savedHistory = getHistory(bookKey);
      if (savedHistory && chapters.length > 0) {
        const savedChapter = chapters.find(ch => ch.idx === savedHistory.chapterIdx);
        if (savedChapter) {
          handleChapterChange(savedChapter);
          // 恢复播放进度需要在媒体加载后设置
        }
      }
    }
  }, [bookKey, chapters, getHistory, handleChapterChange]);

  // 在播放时保存进度
  const saveProgress = useCallback(() => {
    const media = mediaRef.current;
    if (media && bookKey && chapter) {
      addHistory({
        bookKey,
        bookName,
        chapterIdx: currentIdx,
        currentTime: media.currentTime,
        lastPlayed: Date.now()
      });
    }
  }, [bookKey, bookName, currentIdx, chapter, addHistory]);

  // 定期保存进度
  useEffect(() => {
    const interval = setInterval(saveProgress, 30000);
    return () => clearInterval(interval);
  }, [saveProgress]);

  // 在离开页面时保存进度
  useEffect(() => {
    return () => saveProgress();
  }, [saveProgress]);

  if (!bookKey) {
    return <div className="pt-12 text-center text-[13px] text-[#c7c7cc]">缺少 book_key</div>;
  }

  const gradientStyle = useMemo(() => {
    return {
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    };
  }, []);

  return (
    <div className="min-h-screen" style={gradientStyle}>
      <div className="fixed top-0 inset-x-0 z-50 flex items-center px-4 py-3 bg-white/90 backdrop-blur-xl border-b border-black/[0.06]">
        <button onClick={() => navigate(-1)} className="text-[13px] text-[#86868b] mr-4">
          ← 返回
        </button>
        <span className="text-[14px] font-medium text-[#1d1d1f] truncate flex-1">{bookName}</span>
        
        {/* 离线状态和下载按钮 */}
        <div className="flex items-center gap-2">
          {isCurrentChapterCached && (
            <span className="text-[12px] text-green-600 flex items-center gap-1">
              <CheckCircleIcon size={14} />
              已缓存
            </span>
          )}
          
          {downloadProgress && downloadProgress.status === 'downloading' ? (
            <button
              onClick={handleCancelDownload}
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-red-100 text-red-600 text-[12px]"
            >
              <XCircleIcon size={14} />
              取消下载
            </button>
          ) : (
            <button
              onClick={handleDownloadBook}
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-blue-100 text-blue-600 text-[12px]"
              disabled={downloadProgress?.status === 'downloading'}
            >
              <DownloadIcon size={14} />
              {cachedChaptersCount > 0 ? `已缓存 ${cachedChaptersCount}/${chapters.length}` : '下载整本'}
            </button>
          )}
        </div>
      </div>

      <div className="pt-14 pb-32 px-4 sm:px-6 md:px-8 lg:px-12 xl:px-16">
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
          <div className="flex flex-col items-center justify-center py-8 sm:py-12 md:py-16">
            <div className="w-48 h-48 sm:w-56 sm:h-56 md:w-64 md:h-64 lg:w-72 lg:h-72 bg-white/20 rounded-2xl backdrop-blur-sm border border-white/30 flex items-center justify-center mb-6">
              {loading ? (
                <p className="text-[13px] text-white/80">加载中...</p>
              ) : (
                <HeadphonesIcon size={64} className="text-white/60" />
              )}
            </div>
            <h2 className="text-xl sm:text-2xl md:text-3xl font-semibold text-white mb-2 text-center px-4">
              {chapter?.title || "加载中..."}
            </h2>
            <p className="text-sm sm:text-base text-white/80">
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

        {/* 下载进度显示 */}
        {downloadProgress && downloadProgress.status === 'downloading' && (
          <div className="mx-4 mt-4 p-3 rounded-lg bg-blue-50 border border-blue-200">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[13px] text-blue-600 font-medium">正在下载...</p>
              <p className="text-[12px] text-blue-500">
                {downloadProgress.downloadedChapters}/{downloadProgress.totalChapters}
              </p>
            </div>
            <div className="w-full bg-blue-200 rounded-full h-2 mb-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{
                  width: `${(downloadProgress.downloadedChapters / downloadProgress.totalChapters) * 100}%`
                }}
              />
            </div>
            <p className="text-[11px] text-blue-500 truncate">
              当前: {downloadProgress.currentChapter}
            </p>
          </div>
        )}

        {/* 下载完成提示 */}
        {downloadProgress && downloadProgress.status === 'completed' && (
          <div className="mx-4 mt-4 p-3 rounded-lg bg-green-50 border border-green-200">
            <p className="text-[13px] text-green-600 flex items-center gap-2">
              <CheckCircleIcon size={16} />
              下载完成！共缓存 {downloadProgress.totalChapters} 个章节
            </p>
          </div>
        )}

        {/* 下载错误提示 */}
        {downloadProgress && downloadProgress.status === 'error' && (
          <div className="mx-4 mt-4 p-3 rounded-lg bg-red-50 border border-red-200">
            <p className="text-[13px] text-red-600 flex items-center gap-2">
              <XCircleIcon size={16} />
              下载失败: {downloadProgress.error}
            </p>
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
