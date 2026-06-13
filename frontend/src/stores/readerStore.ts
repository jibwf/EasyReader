import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ReaderTheme = "light" | "sepia" | "mint" | "blue" | "gray" | "night" | "dark";
export type NormalizedReaderTheme = Exclude<ReaderTheme, "dark">;

export const AUTO_PAGE_TURN_INTERVAL_MS_MIN = 5000;
export const AUTO_PAGE_TURN_INTERVAL_MS_MAX = 60000;
export const AUTO_PAGE_TURN_INTERVAL_MS_STEP = 500;

export function getDefaultAutoPageTurnIntervalMs(): number {
  if (typeof window === "undefined" || !window.matchMedia) {
    return 10000;
  }
  const isMobileViewport = window.matchMedia("(max-width: 768px)").matches;
  const hasCoarsePointer = window.matchMedia("(pointer: coarse)").matches;
  return isMobileViewport || hasCoarsePointer ? 8000 : 15000;
}

export function clampAutoPageTurnIntervalMs(intervalMs: number): number {
  return Math.min(
    AUTO_PAGE_TURN_INTERVAL_MS_MAX,
    Math.max(AUTO_PAGE_TURN_INTERVAL_MS_MIN, intervalMs)
  );
}

export function normalizeReaderTheme(theme: ReaderTheme): NormalizedReaderTheme {
  return theme === "dark" ? "night" : theme;
}

interface ReaderSettings {
  fontSize: number;
  lineHeight: number;
  theme: ReaderTheme;
  padding: "sm" | "md" | "lg";
  autoPageTurnIntervalMs: number;
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
        autoPageTurnIntervalMs: getDefaultAutoPageTurnIntervalMs(),
      },

      setContent: (content, title, idx) =>
        set({ content, chapterTitle: title, chapterIdx: idx, loading: false }),

      setLoading: (loading) => set({ loading }),

      updateSettings: (partial) =>
        set((state) => ({
          settings: {
            ...state.settings,
            ...partial,
            autoPageTurnIntervalMs: clampAutoPageTurnIntervalMs(
              partial.autoPageTurnIntervalMs ?? state.settings.autoPageTurnIntervalMs
            ),
          },
        })),
    }),
    {
      name: "reader-settings-v2",
      partialize: (state) => ({
        settings: state.settings,
      }),
    }
  )
);
