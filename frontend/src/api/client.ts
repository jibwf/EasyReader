const BASE = "/api";
const REQUEST_TIMEOUT_MS = 45000;
const CLIENT_TYPE = "web-pwa";
const CLIENT_VERSION = __APP_VERSION__;
const API_CONTRACT_VERSION = __API_CONTRACT_VERSION__;

export type SearchMode = "fast" | "full";

function buildHeaders(options?: RequestInit): Headers {
  const headers = getClientRequestHeaders(options?.headers);
  const isFormDataBody = typeof FormData !== "undefined" && options?.body instanceof FormData;

  if (options?.body && !isFormDataBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return headers;
}

function parseDownloadFileName(disposition: string | null, fallback: string): string {
  if (!disposition) {
    return fallback;
  }

  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch?.[1]) {
    try {
      return decodeURIComponent(encodedMatch[1]);
    } catch {
      return encodedMatch[1];
    }
  }

  const plainMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
  if (plainMatch?.[1]) {
    return plainMatch[1];
  }

  return fallback;
}

export function getClientRequestHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init ?? {});
  headers.set("X-Client-Type", CLIENT_TYPE);
  headers.set("X-Client-Version", CLIENT_VERSION);
  headers.set("X-API-Contract-Version", API_CONTRACT_VERSION);

  const token = localStorage.getItem("reader-auth-token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return headers;
}

export function buildSearchStreamUrl(keyword: string, mode: SearchMode = "fast", sources?: string[]) {
  const params = new URLSearchParams();
  params.set("keyword", keyword);
  params.set("mode", mode);
  if (sources?.length) {
    params.set("sources", sources.join(","));
  }
  return `${BASE}/search?${params.toString()}`;
}

export interface BookIdentityQuery {
  bookKey?: string;
  bookUrl?: string;
  sourceUrl?: string;
}

function buildBookIdentityQuery(identity: string | BookIdentityQuery): string {
  const params = new URLSearchParams();
  if (typeof identity === "string") {
    const normalizedBookKey = identity.trim();
    if (!normalizedBookKey) {
      throw new Error("book_key is required");
    }
    params.set("book_key", normalizedBookKey);
    return params.toString();
  }

  const normalizedBookKey = (identity.bookKey || "").trim();
  const normalizedBookUrl = (identity.bookUrl || "").trim();
  const normalizedSourceUrl = (identity.sourceUrl || "").trim();

  if (normalizedBookKey) {
    params.set("book_key", normalizedBookKey);
  }

  if (normalizedBookUrl && normalizedSourceUrl) {
    params.set("book_url", normalizedBookUrl);
    params.set("source_url", normalizedSourceUrl);
  }

  if (params.has("book_key") || (normalizedBookUrl && normalizedSourceUrl)) {
    return params.toString();
  }

  if (normalizedBookUrl || normalizedSourceUrl) {
    throw new Error("book_url and source_url are required together");
  }

  throw new Error("book_key or (book_url + source_url) is required");
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = options?.signal ? null : new AbortController();
  const timeout = controller
    ? window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    : undefined;
  const method = (options?.method || "GET").toUpperCase();
  const cacheMode = method === "GET" ? "default" : "no-store";

  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: buildHeaders(options),
      cache: cacheMode,
      ...options,
      signal: options?.signal ?? controller?.signal,
    });
    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }
    return res.json();
  } finally {
    if (timeout) window.clearTimeout(timeout);
  }
}

export interface SearchResult {
  book_key: string;
  name: string;
  author: string;
  cover_url: string;
  intro: string;
  book_url: string;
  source_url: string;
  source_name: string;
  last_chapter: string;
  kind: string;
}

export interface BookInfo {
  book_key: string;
  name: string;
  author: string;
  cover_url: string;
  intro: string;
  book_url: string;
  source_url: string;
}

export interface Chapter {
  book_key: string;
  title: string;
  url: string;
  idx: number;
}

export interface SourceItem {
  book_source_url: string;
  book_source_name: string;
  book_source_group: string;
  book_source_type: number;
  enabled: boolean;
}

export interface BookItem {
  id: number;
  book_key: string;
  name: string;
  author: string;
  cover_url: string;
  intro: string;
  book_url: string;
  source_url: string;
  category_name: string;
  total_chapters: number;
  server_cached_chapters: number;
}

export interface BookCategoryItem {
  name: string;
  hidden: boolean;
  preset: boolean;
  book_count: number;
}

export interface BatchResultItem {
  book_id: number;
  ok: boolean;
  error?: string;
  cached?: number;
  total?: number;
  format?: string;
  file_name?: string;
  download_url?: string;
  name?: string;
}

export interface SyncProgressPayload {
  user_id: string;
  device_id: string;
  book_key: string;
  book_url: string;
  source_url: string;
  book_name: string;
  chapter_idx: number;
  chapter_title: string;
  chapter_url: string;
  position: number;
  force?: boolean;
}

export interface SyncProgressItem {
  user_id: string;
  device_id: string;
  book_key: string;
  book_url: string;
  source_url: string;
  book_name: string;
  chapter_idx: number;
  chapter_title: string;
  chapter_url: string;
  position: number;
  revision: number;
  updated_at: string;
  accepted: boolean;
  conflict: boolean;
  conflict_reason: string;
}

export interface SyncBookmarkPayloadItem {
  bookmark_id: string;
  book_key: string;
  book_url: string;
  source_url: string;
  book_name: string;
  chapter_idx: number;
  chapter_title: string;
  chapter_url: string;
  position: number;
  quote_text: string;
  note: string;
  deleted: boolean;
}

export interface SyncBookmarkItem extends SyncBookmarkPayloadItem {
  user_id: string;
  device_id: string;
  revision: number;
  updated_at: string;
}

export interface OfflineTaskItem {
  task_id: string;
  user_id: string;
  device_id: string;
  book_id: number;
  book_key: string;
  book_name: string;
  book_url: string;
  source_url: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  total_chapters: number;
  cached_chapters: number;
  error_message: string;
  created_at: string;
  updated_at: string;
  completed_at: string;
}

export interface OfflineCatalogItem {
  user_id: string;
  device_id: string;
  book_id: number;
  book_key: string;
  book_url: string;
  source_url: string;
  name: string;
  author: string;
  total_chapters: number;
  cached_chapters: number;
  updated_at: string;
}

export type BackupRestoreMode = "full" | "incremental";
export type BackupConflictPolicy = "backup_wins" | "local_wins" | "newer_wins";

export interface BackupTableRestoreSummary {
  incoming: number;
  inserted: number;
  updated: number;
  skipped: number;
  conflicts: number;
  resolved_with_backup: number;
  resolved_with_local: number;
}

export interface BackupFileRestoreSummary {
  incoming: number;
  written: number;
  skipped: number;
  conflicts: number;
  resolved_with_backup: number;
  resolved_with_local: number;
}

export interface BackupRestoreResponse {
  ok: boolean;
  format_version: string;
  mode: BackupRestoreMode;
  conflict_policy: BackupConflictPolicy;
  conflicts: number;
  tables: Record<string, BackupTableRestoreSummary>;
  files: Record<string, BackupFileRestoreSummary>;
}

function dedupeLatestSyncProgress(items: SyncProgressItem[]): SyncProgressItem[] {
  const latestByBook = new Map<string, SyncProgressItem>();
  for (const item of items) {
    const previous = latestByBook.get(item.book_key);
    if (!previous || item.revision > previous.revision) {
      latestByBook.set(item.book_key, item);
    }
  }
  return [...latestByBook.values()].sort((a, b) => b.revision - a.revision);
}

export const api = {
  getVersion: () =>
    request<{
      version: string;
      api_contract_version?: string;
      supported_client_types?: string[];
    }>("/version"),

  search: (keyword: string, mode: SearchMode = "fast") =>
    request<SearchResult[]>(`/search?keyword=${encodeURIComponent(keyword)}&mode=${mode}&stream=false`),

  getBookInfo: (identity: string | BookIdentityQuery) =>
    request<BookInfo>(`/content/book-info?${buildBookIdentityQuery(identity)}`),

  getChapters: (identity: string | BookIdentityQuery) =>
    request<Chapter[]>(`/content/chapters?${buildBookIdentityQuery(identity)}`),

  getChapterContent: (url: string, sourceUrl: string) =>
    request<ChapterContent>(
      `/content/chapter?url=${encodeURIComponent(url)}&source_url=${encodeURIComponent(sourceUrl)}`
    ),

  getSources: () => request<SourceItem[]>("/sources"),

  importSources: (sources: unknown[]) =>
    request<{ count: number }>("/sources/import", {
      method: "POST",
      body: JSON.stringify(sources),
    }),

  importSourcesFromUrl: (url: string) =>
    request<{ count: number }>("/sources/import-url", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  toggleSource: (url: string) =>
    request<{ enabled: boolean }>(`/sources/${encodeURIComponent(url)}/toggle`, {
      method: "PUT",
    }),

  deleteSource: (url: string) =>
    request<void>(`/sources/${encodeURIComponent(url)}`, {
      method: "DELETE",
    }),

  getBooks: (options?: { includeHidden?: boolean; category?: string }) => {
    const params = new URLSearchParams();
    if (options?.includeHidden) {
      params.set("include_hidden", "true");
    }
    if (options?.category) {
      params.set("category", options.category);
    }
    const query = params.toString();
    return request<BookItem[]>(`/books${query ? `?${query}` : ""}`);
  },

  addBook: (data: {
    book_key?: string;
    name: string;
    author?: string;
    cover_url?: string;
    intro?: string;
    book_url: string;
    source_url: string;
    total_chapters?: number;
    category_name?: string;
    last_chapter?: string;
  }) =>
    request<{ message: string }>("/books", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getBookCategories: () => request<BookCategoryItem[]>("/books/categories"),

  createBookCategory: (name: string) =>
    request<BookCategoryItem>("/books/categories", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  setBookCategoryHidden: (name: string, hidden: boolean) =>
    request<{ name: string; hidden: boolean }>(`/books/categories/${encodeURIComponent(name)}/hidden`, {
      method: "PUT",
      body: JSON.stringify({ hidden }),
    }),

  renameBookCategory: (name: string, newName: string) =>
    request<{ old_name: string; new_name: string }>(`/books/categories/${encodeURIComponent(name)}/rename`, {
      method: "PUT",
      body: JSON.stringify({ new_name: newName }),
    }),

  deleteBookCategory: (name: string) =>
    request<{ deleted: boolean; name: string; reassigned_to: string }>(
      `/books/categories/${encodeURIComponent(name)}`,
      {
        method: "DELETE",
      }
    ),

  setBookCategory: (bookId: number, categoryName: string) =>
    request<{ message: string; book_id: number; category_name: string }>(`/books/${bookId}/category`, {
      method: "PUT",
      body: JSON.stringify({ category_name: categoryName }),
    }),

  setBookCategoryBatch: (ids: number[], categoryName: string) =>
    request<{ updated: number; requested: number; category_name: string }>("/books/category-batch", {
      method: "POST",
      body: JSON.stringify({ ids, category_name: categoryName }),
    }),

  importBooks: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/books/import`, {
      method: "POST",
      headers: buildHeaders({ body: form }),
      body: form,
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }
    return res.json();
  },

  deleteBook: (bookId: number) =>
    request<{ message: string }>(`/books/${bookId}`, {
      method: "DELETE",
    }),

  deleteBooksBatch: (ids: number[]) =>
    request<{ deleted: number; requested: number }>("/books/delete-batch", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),

  cacheBooksBatch: (ids: number[]) =>
    request<{ success: number; total: number; results: BatchResultItem[] }>("/books/cache-batch", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),

  exportBooksBatch: (ids: number[], format: "txt" | "epub") =>
    request<{ success: number; total: number; format: string; results: BatchResultItem[] }>("/books/export-batch", {
      method: "POST",
      body: JSON.stringify({ ids, format }),
    }),

  getServerCacheStats: () => request<{ books: number; chapters: number; bytes: number }>("/books/cache/stats"),

  clearServerCache: (payload: { ids?: number[]; clear_all?: boolean }) =>
    request<{ cleared: number; clear_all: boolean }>("/books/cache/clear", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  upsertSyncProgress: (data: SyncProgressPayload) =>
    request<SyncProgressItem>("/sync/progress/upsert", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  pullSyncProgress: (userId: string, since = 0, limit = 100) =>
    request<{ items: SyncProgressItem[]; next_cursor: number }>(
      `/sync/progress/pull?user_id=${encodeURIComponent(userId)}&since=${since}&limit=${limit}`
    ),

  pullAllSyncProgress: async (userId: string, limit = 200, maxPages = 10) => {
    const normalizedLimit = Math.max(1, Math.min(limit, 200));
    const normalizedMaxPages = Math.max(1, maxPages);
    let cursor = 0;
    const merged: SyncProgressItem[] = [];

    for (let page = 0; page < normalizedMaxPages; page += 1) {
      const data = await request<{ items: SyncProgressItem[]; next_cursor: number }>(
        `/sync/progress/pull?user_id=${encodeURIComponent(userId)}&since=${cursor}&limit=${normalizedLimit}`
      );

      if (data.items.length === 0) {
        break;
      }

      merged.push(...data.items);

      if (data.items.length < normalizedLimit || data.next_cursor <= cursor) {
        break;
      }

      cursor = data.next_cursor;
    }

    return dedupeLatestSyncProgress(merged);
  },

  upsertSyncBookmarksBatch: (data: {
    user_id: string;
    device_id: string;
    items: SyncBookmarkPayloadItem[];
  }) =>
    request<{ items: SyncBookmarkItem[]; next_cursor: number }>("/sync/bookmarks/batch", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  pullSyncBookmarks: (userId: string, since = 0, limit = 100) =>
    request<{ items: SyncBookmarkItem[]; next_cursor: number }>(
      `/sync/bookmarks/pull?user_id=${encodeURIComponent(userId)}&since=${since}&limit=${limit}`
    ),

  createOfflineTask: (data: {
    user_id: string;
    device_id: string;
    book_id?: number;
    book_key?: string;
    book_url?: string;
    source_url?: string;
  }) =>
    request<OfflineTaskItem>("/offline/tasks", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getOfflineTask: (taskId: string) => request<OfflineTaskItem>(`/offline/tasks/${encodeURIComponent(taskId)}`),

  getOfflineTasks: (userId: string, deviceId: string, limit = 200) =>
    request<OfflineTaskItem[]>(
      `/offline/tasks?user_id=${encodeURIComponent(userId)}&device_id=${encodeURIComponent(deviceId)}&limit=${limit}`
    ),

  getOfflineCatalog: (userId: string, deviceId: string) =>
    request<OfflineCatalogItem[]>(
      `/offline/catalog?user_id=${encodeURIComponent(userId)}&device_id=${encodeURIComponent(deviceId)}`
    ),

  downloadBackup: async () => {
    const res = await fetch(`${BASE}/backup/export`, {
      method: "GET",
      headers: buildHeaders(),
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }

    const fileName = parseDownloadFileName(res.headers.get("content-disposition"), "easyreader-backup.zip");
    const blob = await res.blob();
    return { fileName, blob };
  },

  restoreBackup: async (file: File, mode: BackupRestoreMode, conflictPolicy: BackupConflictPolicy) => {
    const form = new FormData();
    form.append("file", file);

    const params = new URLSearchParams();
    params.set("mode", mode);
    params.set("conflict_policy", conflictPolicy);

    const res = await fetch(`${BASE}/backup/restore?${params.toString()}`, {
      method: "POST",
      headers: buildHeaders({ body: form }),
      body: form,
      cache: "no-store",
    });

    if (!res.ok) {
      let detail = "Backup restore failed";
      try {
        const payload = (await res.json()) as { detail?: string };
        if (payload?.detail) {
          detail = payload.detail;
        }
      } catch {
        // Keep fallback detail.
      }
      throw new Error(detail);
    }

    return (await res.json()) as BackupRestoreResponse;
  },

  scanAudiobooks: () =>
    request<{ scanned: number; imported: number; skipped: number }>("/audiobook/scan", {
      method: "POST",
    }),

  getAudiobookList: () => request<AudiobookItem[]>("/audiobook/list"),

  importAudiobookZip: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/audiobook/import-zip`, {
      method: "POST",
      headers: buildHeaders({ body: form }),
      body: form,
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }
    return res.json();
  },

  deleteAudiobook: (bookId: number) =>
    request<{ deleted: boolean }>(`/audiobook/${bookId}`, {
      method: "DELETE",
    }),
};

export type ChapterContent =
  | { type: "novel"; content: string }
  | { type: "manga"; images: string[] }
  | { type: "audiobook"; manifest: AudiobookManifest };

export interface AudiobookMediaFile {
  filename: string;
  url: string;
  media_type: "audio" | "video";
}

export interface AudiobookManifest {
  media_files: AudiobookMediaFile[];
}

export interface AudiobookItem {
  id: number;
  book_key: string;
  name: string;
  author: string;
  cover_url: string;
  intro: string;
  book_url: string;
  source_url: string;
  category_name: string;
  total_chapters: number;
  media_root: string;
  added_at: string;
  updated_at: string;
}
