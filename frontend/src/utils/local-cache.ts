/**
 * Thin localStorage wrappers for offline fallback data.
 * All values are JSON-serialised. Errors are silently swallowed so callers
 * never have to worry about storage quota issues.
 */

function save(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore QuotaExceededError or private-mode restrictions
  }
}

function load<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

// ── Books list ────────────────────────────────────────────────────────────────

const BOOKS_KEY = "offline_books_cache";

export function saveBooksCache(books: unknown[]): void {
  save(BOOKS_KEY, books);
}

export function loadBooksCache<T>(): T[] {
  return load<T[]>(BOOKS_KEY) ?? [];
}

// ── Offline catalog ───────────────────────────────────────────────────────────

const CATALOG_KEY = "offline_catalog_cache";

export function saveOfflineCatalogCache(items: unknown[]): void {
  save(CATALOG_KEY, items);
}

export function loadOfflineCatalogCache<T>(): T[] {
  return load<T[]>(CATALOG_KEY) ?? [];
}

// ── Chapter list (TOC) — keyed by bookUrl ────────────────────────────────────

const CHAPTERS_PREFIX = "chapters_cache:";

export function saveChaptersCache(bookUrl: string, chapters: unknown[]): void {
  save(`${CHAPTERS_PREFIX}${bookUrl}`, chapters);
}

export function loadChaptersCache<T>(bookUrl: string): T[] {
  return load<T[]>(`${CHAPTERS_PREFIX}${bookUrl}`) ?? [];
}

// ── Offline tasks ─────────────────────────────────────────────────────────────

const TASKS_KEY = "offline_tasks_cache";

export function saveOfflineTasksCache(items: unknown[]): void {
  save(TASKS_KEY, items);
}

export function loadOfflineTasksCache<T>(): T[] {
  return load<T[]>(TASKS_KEY) ?? [];
}
