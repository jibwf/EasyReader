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