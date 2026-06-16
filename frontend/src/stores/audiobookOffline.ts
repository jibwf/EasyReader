import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface OfflineChapter {
  bookKey: string;
  chapterIdx: number;
  chapterTitle: string;
  url: string;
  cachedAt: number;
}

interface DownloadProgress {
  bookKey: string;
  totalChapters: number;
  downloadedChapters: number;
  currentChapter: string;
  status: 'idle' | 'downloading' | 'completed' | 'error';
  error?: string;
}

interface AudiobookOfflineStore {
  // Cached chapters
  cachedChapters: OfflineChapter[];
  
  // Download progress
  downloadProgress: DownloadProgress | null;
  
  // Actions
  addCachedChapter: (chapter: OfflineChapter) => void;
  removeCachedChapter: (bookKey: string, chapterIdx: number) => void;
  isChapterCached: (bookKey: string, chapterIdx: number) => boolean;
  getCachedChapter: (bookKey: string, chapterIdx: number) => OfflineChapter | undefined;
  getBookCachedChapters: (bookKey: string) => OfflineChapter[];
  clearBookCache: (bookKey: string) => void;
  
  // Download actions
  setDownloadProgress: (progress: DownloadProgress | null) => void;
  downloadChapter: (bookKey: string, chapterIdx: number, chapterTitle: string, url: string) => Promise<boolean>;
  downloadEntireBook: (bookKey: string, chapters: { idx: number; title: string; url: string }[]) => Promise<void>;
  cancelDownload: () => void;
  
  // Cache size
  getCacheSize: () => number;
  clearAllCache: () => void;
}

// Cache storage key — must match the Service Worker's cacheName in vite.config.ts
const CACHE_STORAGE_KEY = 'audiobook-media';

export const useAudiobookOffline = create<AudiobookOfflineStore>()(
  persist(
    (set, get) => ({
      cachedChapters: [],
      downloadProgress: null,
      
      addCachedChapter: (chapter) => {
        set((state) => {
          // Check if already cached
          const existing = state.cachedChapters.find(
            c => c.bookKey === chapter.bookKey && c.chapterIdx === chapter.chapterIdx
          );
          if (existing) {
            return state;
          }
          return {
            cachedChapters: [...state.cachedChapters, chapter]
          };
        });
      },
      
      removeCachedChapter: (bookKey, chapterIdx) => {
        set((state) => ({
          cachedChapters: state.cachedChapters.filter(
            c => !(c.bookKey === bookKey && c.chapterIdx === chapterIdx)
          )
        }));
      },
      
      isChapterCached: (bookKey, chapterIdx) => {
        return get().cachedChapters.some(
          c => c.bookKey === bookKey && c.chapterIdx === chapterIdx
        );
      },
      
      getCachedChapter: (bookKey, chapterIdx) => {
        return get().cachedChapters.find(
          c => c.bookKey === bookKey && c.chapterIdx === chapterIdx
        );
      },
      
      getBookCachedChapters: (bookKey) => {
        return get().cachedChapters.filter(c => c.bookKey === bookKey);
      },
      
      clearBookCache: (bookKey) => {
        set((state) => ({
          cachedChapters: state.cachedChapters.filter(c => c.bookKey !== bookKey)
        }));
      },
      
      setDownloadProgress: (progress) => {
        set({ downloadProgress: progress });
      },
      
      downloadChapter: async (bookKey, chapterIdx, chapterTitle, url) => {
        const state = get();
        
        // Check if already cached
        if (state.isChapterCached(bookKey, chapterIdx)) {
          return true;
        }
        
        try {
          // Fetch the audio file
          const response = await fetch(url);
          if (!response.ok) {
            throw new Error(`Failed to download: ${response.statusText}`);
          }
          
          // Store in Cache API
          const cache = await caches.open(CACHE_STORAGE_KEY);
          await cache.put(url, response);
          
          // Record in store
          state.addCachedChapter({
            bookKey,
            chapterIdx,
            chapterTitle,
            url,
            cachedAt: Date.now()
          });
          
          return true;
        } catch (error) {
          console.error('Failed to download chapter:', error);
          return false;
        }
      },
      
      downloadEntireBook: async (bookKey, chapters) => {
        const state = get();
        
        // Initialize progress
        state.setDownloadProgress({
          bookKey,
          totalChapters: chapters.length,
          downloadedChapters: 0,
          currentChapter: '',
          status: 'downloading'
        });
        
        for (let i = 0; i < chapters.length; i++) {
          const chapter = chapters[i];
          
          // Check if download was cancelled
          if (get().downloadProgress?.status !== 'downloading') {
            break;
          }
          
          // Update progress
          state.setDownloadProgress({
            ...get().downloadProgress!,
            currentChapter: chapter.title,
            downloadedChapters: i
          });
          
          // Download chapter
          const success = await state.downloadChapter(
            bookKey,
            chapter.idx,
            chapter.title,
            chapter.url
          );
          
          if (!success) {
            state.setDownloadProgress({
              ...get().downloadProgress!,
              status: 'error',
              error: `Failed to download chapter: ${chapter.title}`
            });
            return;
          }
        }
        
        // Mark as completed
        state.setDownloadProgress({
          ...get().downloadProgress!,
          status: 'completed',
          downloadedChapters: chapters.length
        });
        
        // Clear progress after 2 seconds
        setTimeout(() => {
          state.setDownloadProgress(null);
        }, 2000);
      },
      
      cancelDownload: () => {
        set((state) => ({
          downloadProgress: state.downloadProgress ? {
            ...state.downloadProgress,
            status: 'idle'
          } : null
        }));
      },
      
      getCacheSize: () => {
        return get().cachedChapters.length;
      },
      
      clearAllCache: () => {
        set({ cachedChapters: [] });
        // Also clear Cache API
        caches.delete(CACHE_STORAGE_KEY);
      }
    }),
    {
      name: 'audiobook-offline',
      partialize: (state) => ({
        cachedChapters: state.cachedChapters
      })
    }
  )
);