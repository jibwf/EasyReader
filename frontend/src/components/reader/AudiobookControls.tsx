import { useRef, useState, useEffect, useCallback, type RefObject } from "react";
import type { Chapter } from "@/api/client";

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 2];
const SLEEP_TIMER_OPTIONS = [
  { label: "关闭", value: null },
  { label: "15 分钟", value: 15 },
  { label: "30 分钟", value: 30 },
  { label: "45 分钟", value: 45 },
  { label: "60 分钟", value: 60 },
  { label: "90 分钟", value: 90 },
];

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatRemaining(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface AudiobookControlsProps {
  mediaRef: RefObject<HTMLVideoElement | HTMLAudioElement>;
  chapters: Chapter[];
  currentIdx: number;
  onChapterChange: (chapter: Chapter) => void;
  showVideo: boolean;
  onToggleVideo: () => void;
  hasVideo: boolean;
}

export default function AudiobookControls({
  mediaRef,
  chapters,
  currentIdx,
  onChapterChange,
  showVideo,
  onToggleVideo,
  hasVideo,
}: AudiobookControlsProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(() => {
    const saved = localStorage.getItem("audiobook-playback-rate");
    return saved ? parseFloat(saved) : 1;
  });
  const [showRateMenu, setShowRateMenu] = useState(false);
  const [showSleepMenu, setShowSleepMenu] = useState(false);
  const [sleepTimerMinutes, setSleepTimerMinutes] = useState<number | null>(null);
  const [sleepTimerRemaining, setSleepTimerRemaining] = useState<number | null>(null);
  const sleepTimerRef = useRef<ReturnType<typeof setInterval>>();
  const progressRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const media = mediaRef.current;
    if (!media) return;

    setReady(false);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onTimeUpdate = () => { if (!dragging) setCurrentTime(media.currentTime); };
    const onDurationChange = () => setDuration(media.duration || 0);
    const onEnded = () => {
      const next = chapters.find((ch) => ch.idx === currentIdx + 1);
      if (next) onChapterChange(next);
    };
    const onCanPlay = () => setReady(true);

    media.addEventListener("play", onPlay);
    media.addEventListener("pause", onPause);
    media.addEventListener("timeupdate", onTimeUpdate);
    media.addEventListener("durationchange", onDurationChange);
    media.addEventListener("ended", onEnded);
    media.addEventListener("canplay", onCanPlay);

    return () => {
      media.removeEventListener("play", onPlay);
      media.removeEventListener("pause", onPause);
      media.removeEventListener("timeupdate", onTimeUpdate);
      media.removeEventListener("durationchange", onDurationChange);
      media.removeEventListener("ended", onEnded);
      media.removeEventListener("canplay", onCanPlay);
    };
  }, [mediaRef, chapters, currentIdx, onChapterChange, dragging]);

  useEffect(() => {
    const media = mediaRef.current;
    if (!media) return;
    media.playbackRate = playbackRate;
    localStorage.setItem("audiobook-playback-rate", String(playbackRate));
  }, [playbackRate, mediaRef]);

  useEffect(() => {
    if (!("mediaSession" in navigator)) return;
    const chapter = chapters.find((ch) => ch.idx === currentIdx);
    navigator.mediaSession.metadata = new MediaMetadata({
      title: chapter?.title || "",
      artist: "",
      album: "",
    });
    navigator.mediaSession.setActionHandler("play", () => mediaRef.current?.play());
    navigator.mediaSession.setActionHandler("pause", () => mediaRef.current?.pause());
    navigator.mediaSession.setActionHandler("seekbackward", () => {
      if (mediaRef.current) mediaRef.current.currentTime -= 15;
    });
    navigator.mediaSession.setActionHandler("seekforward", () => {
      if (mediaRef.current) mediaRef.current.currentTime += 15;
    });
    navigator.mediaSession.setActionHandler("previoustrack", () => {
      const prev = chapters.find((ch) => ch.idx === currentIdx - 1);
      if (prev) onChapterChange(prev);
    });
    navigator.mediaSession.setActionHandler("nexttrack", () => {
      const next = chapters.find((ch) => ch.idx === currentIdx + 1);
      if (next) onChapterChange(next);
    });
    return () => {
      navigator.mediaSession.setActionHandler("play", null);
      navigator.mediaSession.setActionHandler("pause", null);
      navigator.mediaSession.setActionHandler("seekbackward", null);
      navigator.mediaSession.setActionHandler("seekforward", null);
      navigator.mediaSession.setActionHandler("previoustrack", null);
      navigator.mediaSession.setActionHandler("nexttrack", null);
    };
  }, [chapters, currentIdx, mediaRef, onChapterChange]);

  useEffect(() => {
    if (!("mediaSession" in navigator)) return;
    navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";
  }, [isPlaying]);

  const startSleepTimer = useCallback((minutes: number | null) => {
    if (sleepTimerRef.current) clearInterval(sleepTimerRef.current);
    setSleepTimerMinutes(minutes);
    setShowSleepMenu(false);
    if (minutes === null) {
      setSleepTimerRemaining(null);
      return;
    }
    setSleepTimerRemaining(minutes * 60);
    sleepTimerRef.current = setInterval(() => {
      setSleepTimerRemaining((prev) => {
        if (prev === null || prev <= 1) {
          if (sleepTimerRef.current) clearInterval(sleepTimerRef.current);
          mediaRef.current?.pause();
          return null;
        }
        return prev - 1;
      });
    }, 1000);
  }, [mediaRef]);

  useEffect(() => {
    return () => { if (sleepTimerRef.current) clearInterval(sleepTimerRef.current); };
  }, []);

  const togglePlay = () => {
    const media = mediaRef.current;
    if (!media || !ready) return;
    if (media.paused) media.play().catch(() => {});
    else media.pause();
  };

  const seekBy = (delta: number) => {
    const media = mediaRef.current;
    if (!media) return;
    media.currentTime = Math.max(0, Math.min(media.duration || 0, media.currentTime + delta));
  };

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const bar = progressRef.current;
    const media = mediaRef.current;
    if (!bar || !media || !duration) return;
    const rect = bar.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    media.currentTime = ratio * duration;
    setCurrentTime(ratio * duration);
  };

  const handleProgressMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setDragging(true);
    handleProgressClick(e);
    const onMove = (ev: MouseEvent) => {
      const bar = progressRef.current;
      const media = mediaRef.current;
      if (!bar || !media || !duration) return;
      const rect = bar.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
      setCurrentTime(ratio * duration);
    };
    const onUp = (ev: MouseEvent) => {
      setDragging(false);
      const bar = progressRef.current;
      const media = mediaRef.current;
      if (bar && media && duration) {
        const rect = bar.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
        media.currentTime = ratio * duration;
      }
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const hasPrev = chapters.some((ch) => ch.idx === currentIdx - 1);
  const hasNext = chapters.some((ch) => ch.idx === currentIdx + 1);
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="w-full">
      {/* Progress bar */}
      <div className="px-4 mb-4">
        <div
          ref={progressRef}
          className="relative h-1 bg-white/30 rounded-full cursor-pointer group"
          onMouseDown={handleProgressMouseDown}
        >
          <div
            className="absolute inset-y-0 left-0 bg-white rounded-full"
            style={{ width: `${progress}%` }}
          />
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ left: `calc(${progress}% - 6px)` }}
          />
        </div>
        <div className="flex justify-between text-xs text-white/70 mt-1 tabular-nums">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>

      {/* Main controls */}
      <div className="flex items-center justify-center gap-6 px-4 py-4">
        <button
          onClick={() => { const prev = chapters.find((ch) => ch.idx === currentIdx - 1); if (prev) onChapterChange(prev); }}
          disabled={!hasPrev}
          className="text-white/80 text-2xl disabled:opacity-30"
        >
          ⏮
        </button>
        <button
          onClick={() => seekBy(-15)}
          className="text-white/80 text-lg"
        >
          ⏪15
        </button>
        <button
          onClick={togglePlay}
          className="bg-white text-[#667eea] w-16 h-16 rounded-full flex items-center justify-center text-2xl shadow-lg active:bg-white/90"
        >
          {isPlaying ? "⏸" : "▶"}
        </button>
        <button
          onClick={() => seekBy(15)}
          className="text-white/80 text-lg"
        >
          15⏩
        </button>
        <button
          onClick={() => { const next = chapters.find((ch) => ch.idx === currentIdx + 1); if (next) onChapterChange(next); }}
          disabled={!hasNext}
          className="text-white/80 text-2xl disabled:opacity-30"
        >
          ⏭
        </button>
      </div>

      {/* Bottom bar */}
      <div className="flex items-center justify-around px-4 py-4 border-t border-white/20">
        <div className="relative">
          <button
            onClick={() => { setShowSleepMenu(!showSleepMenu); setShowRateMenu(false); }}
            className="flex flex-col items-center"
          >
            <span className="text-xl mb-1">⏰</span>
            <span className="text-xs text-white/70">
              {sleepTimerRemaining !== null ? formatRemaining(sleepTimerRemaining) : "定时"}
            </span>
          </button>
          {showSleepMenu && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-white rounded-xl shadow-xl border border-black/[0.06] py-1 z-50 min-w-[120px]">
              {SLEEP_TIMER_OPTIONS.map((opt) => (
                <button
                  key={String(opt.value)}
                  onClick={() => startSleepTimer(opt.value)}
                  className={`block w-full text-left px-4 py-2 text-[13px] hover:bg-black/[0.03] ${
                    sleepTimerMinutes === opt.value ? "text-[#667eea] font-medium" : "text-[#1d1d1f]"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
        
        <div className="relative">
          <button
            onClick={() => { setShowRateMenu(!showRateMenu); setShowSleepMenu(false); }}
            className="flex flex-col items-center"
          >
            <span className="text-xl mb-1">🔊</span>
            <span className="text-xs text-white/70 tabular-nums">{playbackRate}x</span>
          </button>
          {showRateMenu && (
            <div className="absolute bottom-full right-0 mb-2 bg-white rounded-xl shadow-xl border border-black/[0.06] py-1 z-50 min-w-[80px]">
              {PLAYBACK_RATES.map((rate) => (
                <button
                  key={rate}
                  onClick={() => { setPlaybackRate(rate); setShowRateMenu(false); }}
                  className={`block w-full text-left px-4 py-2 text-[13px] hover:bg-black/[0.03] ${
                    playbackRate === rate ? "text-[#667eea] font-medium" : "text-[#1d1d1f]"
                  }`}
                >
                  {rate}x
                </button>
              ))}
            </div>
          )}
        </div>
        
        {hasVideo && (
          <button
            onClick={onToggleVideo}
            className="flex flex-col items-center"
          >
            <span className="text-xl mb-1">🎬</span>
            <span className="text-xs text-white/70">{showVideo ? "纯音频" : "显示画面"}</span>
          </button>
        )}
        
        <button className="flex flex-col items-center">
          <span className="text-xl mb-1">📋</span>
          <span className="text-xs text-white/70">目录</span>
        </button>
        
        <button className="flex flex-col items-center">
          <span className="text-xl mb-1">❤️</span>
          <span className="text-xs text-white/70">收藏</span>
        </button>
      </div>

      {/* Inline chapter list */}
      {chapters.length > 0 && (
        <div className="mt-4 border-t border-white/20 pt-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-white/70 mb-2 px-1">
            目录 · {chapters.length} 章
          </h4>
          <div className="max-h-[300px] overflow-y-auto">
            {chapters.map((ch) => (
              <button
                key={ch.idx}
                onClick={() => onChapterChange(ch)}
                className={`block w-full text-left px-3 py-2 text-sm truncate rounded transition-colors ${
                  ch.idx === currentIdx
                    ? "text-white font-medium bg-white/20"
                    : "text-white/80 hover:bg-white/10"
                }`}
              >
                {ch.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
