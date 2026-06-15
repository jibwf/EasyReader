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