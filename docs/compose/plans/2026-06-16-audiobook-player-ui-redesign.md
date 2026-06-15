# 有声书播放界面UI重新设计实施计划

> [!NOTE]
> This document may not reflect the current implementation.
> See the final report for up-to-date state:
> [Final Report](../reports/audiobook-player-ui-redesign.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重新设计有声书播放界面，采用喜马拉雅风格，并增加播放历史、播放列表和收藏功能。

**Architecture:** 基于现有React组件重构，使用Tailwind CSS实现渐变效果，添加新的功能模块。

**Tech Stack:** React, TypeScript, Tailwind CSS, zustand

---

### Task 1: 重构AudiobookPlayer.tsx组件

**Covers:** [S3]

**Files:**
- Modify: `frontend/src/pages/AudiobookPlayer.tsx`

- [ ] **Step 1: 添加渐变色背景**

```tsx
// 在AudiobookPlayer.tsx中添加渐变色背景
const gradientStyle = {
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
};

return (
  <div className="min-h-screen" style={gradientStyle}>
    {/* 现有内容 */}
  </div>
);
```

- [ ] **Step 2: 重新设计封面区域**

```tsx
// 重新设计封面区域
<div className="flex flex-col items-center justify-center py-8">
  <div className="w-48 h-48 bg-white/20 rounded-2xl backdrop-blur-sm border border-white/30 flex items-center justify-center mb-6">
    <span className="text-6xl">🎧</span>
  </div>
  <h2 className="text-xl font-semibold text-white mb-2">
    {chapter?.title || "加载中..."}
  </h2>
  <p className="text-sm text-white/80">
    {chapters.length > 0 ? `第 ${currentIdx + 1} / ${chapters.length} 章` : ""}
  </p>
</div>
```

- [ ] **Step 3: 重新设计控制按钮区域**

```tsx
// 重新设计控制按钮区域
<div className="flex items-center justify-center gap-6 py-6">
  <button className="text-white/80 text-2xl">⏮</button>
  <button className="text-white/80 text-lg">⏪15</button>
  <button className="bg-white text-[#667eea] w-16 h-16 rounded-full flex items-center justify-center text-2xl shadow-lg">
    {isPlaying ? "⏸" : "▶"}
  </button>
  <button className="text-white/80 text-lg">15⏩</button>
  <button className="text-white/80 text-2xl">⏭</button>
</div>
```

- [ ] **Step 4: 重新设计底部设置栏**

```tsx
// 重新设计底部设置栏
<div className="flex justify-around py-4 border-t border-white/20">
  <div className="text-center">
    <div className="text-xl mb-1">⏰</div>
    <div className="text-xs text-white/70">定时</div>
  </div>
  <div className="text-center">
    <div className="text-xl mb-1">🔊</div>
    <div className="text-xs text-white/70">{playbackRate}x</div>
  </div>
  <div className="text-center">
    <div className="text-xl mb-1">📋</div>
    <div className="text-xs text-white/70">目录</div>
  </div>
  <div className="text-center">
    <div className="text-xl mb-1">❤️</div>
    <div className="text-xs text-white/70">收藏</div>
  </div>
</div>
```

- [ ] **Step 5: 运行测试验证**

Run: `npm run typecheck`
Expected: 无类型错误

- [ ] **Step 6: 提交更改**

```bash
git add frontend/src/pages/AudiobookPlayer.tsx
git commit -m "refactor: 重构AudiobookPlayer组件，采用喜马拉雅风格"
```

### Task 2: 重构AudiobookControls.tsx组件

**Covers:** [S3]

**Files:**
- Modify: `frontend/src/components/reader/AudiobookControls.tsx`

- [ ] **Step 1: 重新设计进度条**

```tsx
// 重新设计进度条
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
```

- [ ] **Step 2: 重新设计主控制按钮**

```tsx
// 重新设计主控制按钮
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
```

- [ ] **Step 3: 重新设计底部设置栏**

```tsx
// 重新设计底部设置栏
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
```

- [ ] **Step 4: 重新设计章节列表**

```tsx
// 重新设计章节列表
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
```

- [ ] **Step 5: 运行测试验证**

Run: `npm run typecheck`
Expected: 无类型错误

- [ ] **Step 6: 提交更改**

```bash
git add frontend/src/components/reader/AudiobookControls.tsx
git commit -m "refactor: 重构AudiobookControls组件，采用喜马拉雅风格"
```

### Task 3: 添加播放历史功能

**Covers:** [S3]

**Files:**
- Create: `frontend/src/stores/audiobookHistory.ts`
- Modify: `frontend/src/pages/AudiobookPlayer.tsx`

- [ ] **Step 1: 创建播放历史store**

```typescript
// frontend/src/stores/audiobookHistory.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AudiobookHistory {
  bookKey: string;
  bookName: string;
  chapterIdx: number;
  currentTime: number;
  lastPlayed: number;
}

interface AudiobookHistoryStore {
  history: AudiobookHistory[];
  addHistory: (history: AudiobookHistory) => void;
  getHistory: (bookKey: string) => AudiobookHistory | undefined;
  removeHistory: (bookKey: string) => void;
}

export const useAudiobookHistory = create<AudiobookHistoryStore>()(
  persist(
    (set, get) => ({
      history: [],
      addHistory: (newHistory) => {
        set((state) => {
          const existingIndex = state.history.findIndex(h => h.bookKey === newHistory.bookKey);
          if (existingIndex >= 0) {
            const newHistoryArray = [...state.history];
            newHistoryArray[existingIndex] = newHistory;
            return { history: newHistoryArray };
          }
          return { history: [...state.history, newHistory] };
        });
      },
      getHistory: (bookKey) => {
        return get().history.find(h => h.bookKey === bookKey);
      },
      removeHistory: (bookKey) => {
        set((state) => ({
          history: state.history.filter(h => h.bookKey !== bookKey)
        }));
      }
    }),
    { name: 'audiobook-history' }
  )
);
```

- [ ] **Step 2: 在AudiobookPlayer中集成播放历史**

```tsx
// 在AudiobookPlayer.tsx中集成播放历史
import { useAudiobookHistory } from '@/stores/audiobookHistory';

export default function AudiobookPlayer() {
  const { addHistory, getHistory } = useAudiobookHistory();
  
  // 在加载书籍时恢复播放进度
  useEffect(() => {
    if (bookKey) {
      const savedHistory = getHistory(bookKey);
      if (savedHistory && chapters.length > 0) {
        const chapter = chapters.find(ch => ch.idx === savedHistory.chapterIdx);
        if (chapter) {
          handleChapterChange(chapter);
          // 恢复播放进度需要在媒体加载后设置
        }
      }
    }
  }, [bookKey, chapters, getHistory]);
  
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
}
```

- [ ] **Step 3: 运行测试验证**

Run: `npm run typecheck`
Expected: 无类型错误

- [ ] **Step 4: 提交更改**

```bash
git add frontend/src/stores/audiobookHistory.ts frontend/src/pages/AudiobookPlayer.tsx
git commit -m "feat: 添加播放历史功能"
```

### Task 4: 添加播放列表功能

**Covers:** [S3]

**Files:**
- Create: `frontend/src/stores/audiobookPlaylist.ts`
- Modify: `frontend/src/pages/AudiobookPlayer.tsx`

- [ ] **Step 1: 创建播放列表store**

```typescript
// frontend/src/stores/audiobookPlaylist.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface PlaylistItem {
  bookKey: string;
  bookName: string;
  chapterIdx: number;
}

interface AudiobookPlaylist {
  id: string;
  name: string;
  items: PlaylistItem[];
  createdAt: number;
}

interface AudiobookPlaylistStore {
  playlists: AudiobookPlaylist[];
  createPlaylist: (name: string) => void;
  deletePlaylist: (id: string) => void;
  addToPlaylist: (playlistId: string, item: PlaylistItem) => void;
  removeFromPlaylist: (playlistId: string, bookKey: string) => void;
  getPlaylists: () => AudiobookPlaylist[];
}

export const useAudiobookPlaylist = create<AudiobookPlaylistStore>()(
  persist(
    (set, get) => ({
      playlists: [],
      createPlaylist: (name) => {
        const newPlaylist: AudiobookPlaylist = {
          id: Date.now().toString(),
          name,
          items: [],
          createdAt: Date.now()
        };
        set((state) => ({
          playlists: [...state.playlists, newPlaylist]
        }));
      },
      deletePlaylist: (id) => {
        set((state) => ({
          playlists: state.playlists.filter(p => p.id !== id)
        }));
      },
      addToPlaylist: (playlistId, item) => {
        set((state) => ({
          playlists: state.playlists.map(p => {
            if (p.id === playlistId) {
              return { ...p, items: [...p.items, item] };
            }
            return p;
          })
        }));
      },
      removeFromPlaylist: (playlistId, bookKey) => {
        set((state) => ({
          playlists: state.playlists.map(p => {
            if (p.id === playlistId) {
              return { ...p, items: p.items.filter(i => i.bookKey !== bookKey) };
            }
            return p;
          })
        }));
      },
      getPlaylists: () => {
        return get().playlists;
      }
    }),
    { name: 'audiobook-playlists' }
  )
);
```

- [ ] **Step 2: 在AudiobookPlayer中集成播放列表**

```tsx
// 在AudiobookPlayer.tsx中集成播放列表
import { useAudiobookPlaylist } from '@/stores/audiobookPlaylist';

export default function AudiobookPlayer() {
  const { createPlaylist, addToPlaylist, getPlaylists } = useAudiobookPlaylist();
  
  // 添加到播放列表功能
  const handleAddToPlaylist = useCallback((playlistId: string) => {
    if (bookKey && chapter) {
      addToPlaylist(playlistId, {
        bookKey,
        bookName,
        chapterIdx: currentIdx
      });
    }
  }, [bookKey, bookName, currentIdx, chapter, addToPlaylist]);
  
  // 创建新播放列表
  const handleCreatePlaylist = useCallback((name: string) => {
    createPlaylist(name);
  }, [createPlaylist]);
}
```

- [ ] **Step 3: 运行测试验证**

Run: `npm run typecheck`
Expected: 无类型错误

- [ ] **Step 4: 提交更改**

```bash
git add frontend/src/stores/audiobookPlaylist.ts frontend/src/pages/AudiobookPlayer.tsx
git commit -m "feat: 添加播放列表功能"
```

### Task 5: 添加收藏功能

**Covers:** [S3]

**Files:**
- Create: `frontend/src/stores/audiobookFavorites.ts`
- Modify: `frontend/src/pages/AudiobookPlayer.tsx`

- [ ] **Step 1: 创建收藏store**

```typescript
// frontend/src/stores/audiobookFavorites.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AudiobookFavorite {
  bookKey: string;
  bookName: string;
  addedAt: number;
}

interface AudiobookFavoritesStore {
  favorites: AudiobookFavorite[];
  addFavorite: (favorite: AudiobookFavorite) => void;
  removeFavorite: (bookKey: string) => void;
  isFavorite: (bookKey: string) => boolean;
  getFavorites: () => AudiobookFavorite[];
}

export const useAudiobookFavorites = create<AudiobookFavoritesStore>()(
  persist(
    (set, get) => ({
      favorites: [],
      addFavorite: (newFavorite) => {
        set((state) => {
          if (state.favorites.some(f => f.bookKey === newFavorite.bookKey)) {
            return state;
          }
          return { favorites: [...state.favorites, newFavorite] };
        });
      },
      removeFavorite: (bookKey) => {
        set((state) => ({
          favorites: state.favorites.filter(f => f.bookKey !== bookKey)
        }));
      },
      isFavorite: (bookKey) => {
        return get().favorites.some(f => f.bookKey === bookKey);
      },
      getFavorites: () => {
        return get().favorites;
      }
    }),
    { name: 'audiobook-favorites' }
  )
);
```

- [ ] **Step 2: 在AudiobookPlayer中集成收藏功能**

```tsx
// 在AudiobookPlayer.tsx中集成收藏功能
import { useAudiobookFavorites } from '@/stores/audiobookFavorites';

export default function AudiobookPlayer() {
  const { addFavorite, removeFavorite, isFavorite } = useAudiobookFavorites();
  
  // 切换收藏状态
  const handleToggleFavorite = useCallback(() => {
    if (bookKey && bookName) {
      if (isFavorite(bookKey)) {
        removeFavorite(bookKey);
      } else {
        addFavorite({
          bookKey,
          bookName,
          addedAt: Date.now()
        });
      }
    }
  }, [bookKey, bookName, isFavorite, addFavorite, removeFavorite]);
  
  // 检查是否已收藏
  const isCurrentlyFavorite = bookKey ? isFavorite(bookKey) : false;
}
```

- [ ] **Step 3: 运行测试验证**

Run: `npm run typecheck`
Expected: 无类型错误

- [ ] **Step 4: 提交更改**

```bash
git add frontend/src/stores/audiobookFavorites.ts frontend/src/pages/AudiobookPlayer.tsx
git commit -m "feat: 添加收藏功能"
```

### Task 6: 测试和优化

**Covers:** [S5]

**Files:**
- Modify: `frontend/src/pages/AudiobookPlayer.tsx`
- Modify: `frontend/src/components/reader/AudiobookControls.tsx`

- [ ] **Step 1: 运行完整测试**

Run: `npm run typecheck && npm run build`
Expected: 无错误，构建成功

- [ ] **Step 2: 优化性能**

```tsx
// 优化渐变色生成，避免不必要的重新计算
const gradientStyle = useMemo(() => {
  // 从封面图提取主色调的逻辑
  return {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
  };
}, []);
```

- [ ] **Step 3: 优化响应式设计**

```tsx
// 确保在不同屏幕尺寸下都能良好显示
<div className="min-h-screen px-4 py-8">
  <div className="max-w-md mx-auto">
    {/* 内容 */}
  </div>
</div>
```

- [ ] **Step 4: 提交最终更改**

```bash
git add frontend/src/pages/AudiobookPlayer.tsx frontend/src/components/reader/AudiobookControls.tsx
git commit -m "chore: 优化播放器性能和响应式设计"
```