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