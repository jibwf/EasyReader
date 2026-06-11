import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ReaderTheme = "light" | "sepia" | "mint" | "blue" | "gray" | "night" | "dark";
export type NormalizedReaderTheme = Exclude<ReaderTheme, "dark">;
export type AutoPageTurnSpeed = "slow" | "medium" | "fast";

export function normalizeReaderTheme(theme: ReaderTheme): NormalizedReaderTheme {
  return theme === "dark" ? "night" : theme;
}

interface ReaderSettings {
  fontSize: number;
  lineHeight: number;
  theme: ReaderTheme;
  padding: "sm" | "md" | "lg";
  autoPageTurnSpeed: AutoPageTurnSpeed;
}

interface ReaderState {
  content: string;
  chapterTitle: string;
  chapterIdx: number;
  loading: boolean;
  settings: ReaderSettings;
  setContent: (content: string, title: string, idx: number) => void;
  setLoading: (loading: boolean) => void;
  updateSettings: (partial: Partial<ReaderSettings>) => void;
}

export const useReaderStore = create<ReaderState>()(
  persist(
    (set) => ({
      content: "",
      chapterTitle: "",
      chapterIdx: 0,
      loading: false,
      settings: {
        fontSize: 18,
        lineHeight: 1.8,
        theme: "light",
        padding: "md",
        autoPageTurnSpeed: "medium",
      },

      setContent: (content, title, idx) =>
        set({ content, chapterTitle: title, chapterIdx: idx, loading: false }),

      setLoading: (loading) => set({ loading }),

      updateSettings: (partial) =>
        set((state) => ({
          settings: { ...state.settings, ...partial },
        })),
    }),
    {
      name: "reader-settings",
      partialize: (state) => ({
        settings: state.settings,
      }),
    }
  )
);
