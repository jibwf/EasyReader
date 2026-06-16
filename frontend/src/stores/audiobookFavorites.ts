import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AudiobookFavorite {
  bookKey: string;
  bookName: string;
  addedAt: number;
}

interface AudiobookFavoritesStore {
  favorites: AudiobookFavorite[];
  addFavorite: (bookKey: string, bookName: string) => void;
  removeFavorite: (bookKey: string) => void;
  isFavorite: (bookKey: string) => boolean;
}

export const useAudiobookFavorites = create<AudiobookFavoritesStore>()(
  persist(
    (set, get) => ({
      favorites: [],
      
      addFavorite: (bookKey, bookName) => {
        set((state) => {
          if (state.favorites.some(f => f.bookKey === bookKey)) {
            return state;
          }
          return {
            favorites: [...state.favorites, { bookKey, bookName, addedAt: Date.now() }]
          };
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
    }),
    { name: 'audiobook-favorites' }
  )
);
