import { create } from "zustand";
import { SearchResult, Chapter, SearchMode, api, buildSearchStreamUrl, getClientRequestHeaders } from "@/api/client";

function resultKey(item: SearchResult): string {
  return `${item.name}|${item.author}|${item.source_url}|${item.book_url}`.toLowerCase();
}

function mergeStableResults(current: SearchResult[], incoming: SearchResult[]): SearchResult[] {
  const seen = new Set(current.map(resultKey));
  const merged = [...current];
  for (const item of incoming) {
    const key = resultKey(item);
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  return merged;
}

interface BookState {
  searchResults: SearchResult[];
  searchKeyword: string;
  searchMode: SearchMode;
  fullSearchRunning: boolean;
  fullSearchDone: boolean;
  chapters: Chapter[];
  loading: boolean;
  error: string;
  search: (keyword: string, options?: { mode?: SearchMode; append?: boolean }) => Promise<void>;
  loadChapters: (bookKey: string) => Promise<void>;
}

export const useBookStore = create<BookState>((set, get) => ({
  searchResults: [],
  searchKeyword: "",
  searchMode: "fast",
  fullSearchRunning: false,
  fullSearchDone: false,
  chapters: [],
  loading: false,
  error: "",

  search: async (keyword: string, options?: { mode?: SearchMode; append?: boolean }) => {
    const mode = options?.mode || "fast";
    const append = options?.append ?? mode === "full";
    const normalizedKeyword = keyword.trim();
    if (!normalizedKeyword) {
      set({
        searchResults: [],
        searchKeyword: "",
        loading: false,
        error: "",
        searchMode: mode,
        fullSearchRunning: false,
        fullSearchDone: false,
      });
      return;
    }

    const current = get();
    if (
      mode === "fast" &&
      current.searchKeyword === normalizedKeyword &&
      current.searchMode === "fast" &&
      (current.loading || current.searchResults.length > 0)
    ) {
      return;
    }

    set((state) => ({
      searchResults: append && state.searchKeyword === normalizedKeyword ? state.searchResults : [],
      searchKeyword: normalizedKeyword,
      searchMode: mode,
      loading: true,
      error: "",
      fullSearchRunning: mode === "full",
      fullSearchDone: mode === "fast" ? false : state.fullSearchDone,
    }));

    try {
      const response = await fetch(
        buildSearchStreamUrl(normalizedKeyword, mode),
        {
          headers: getClientRequestHeaders(),
          cache: "no-store",
        }
      );
      if (!response.ok) throw new Error(`Search failed: ${response.status}`);
      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          if (payload === "[DONE]") break;

          try {
            const batch: SearchResult[] = JSON.parse(payload);
            set((state) => ({
              searchResults: state.searchKeyword === normalizedKeyword
                ? mergeStableResults(state.searchResults, batch)
                : state.searchResults,
            }));
          } catch {
            // skip malformed lines
          }
        }
      }
    } catch (e) {
      if (get().searchKeyword === normalizedKeyword) {
        set({ error: String(e) });
      }
    } finally {
      if (get().searchKeyword === normalizedKeyword) {
        set((state) => ({
          loading: false,
          fullSearchRunning: false,
          fullSearchDone: mode === "full" ? true : state.fullSearchDone,
        }));
      }
    }
  },

  loadChapters: async (bookKey: string) => {
    set({ loading: true, error: "" });
    try {
      const chapters = await api.getChapters(bookKey);
      set({ chapters, loading: false });
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },
}));
