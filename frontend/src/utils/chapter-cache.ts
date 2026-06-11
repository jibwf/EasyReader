import { clear, del, get, keys, set, setMany } from "idb-keyval";

const CHAPTER_PREFIX = "ch:";
const BOOK_INDEX_PREFIX = "book-chapters:";
const BOOK_CHAPTER_IDX_PREFIX = "book-chapter-idx:";

function indexKey(bookUrl: string) {
  return `${BOOK_INDEX_PREFIX}${bookUrl}`;
}

function chapterIdxKey(bookUrl: string, chapterIdx: number) {
  return `${BOOK_CHAPTER_IDX_PREFIX}${bookUrl}:${chapterIdx}`;
}

function normalizeChapterUrl(chapterUrl: string) {
  return chapterUrl.trim().replace(/\/+$/, "");
}

function chapterKey(chapterUrl: string) {
  return `${CHAPTER_PREFIX}${normalizeChapterUrl(chapterUrl)}`;
}

function normalizeStoredChapterKey(storedKey: string) {
  if (storedKey.startsWith(CHAPTER_PREFIX)) {
    return chapterKey(storedKey.slice(CHAPTER_PREFIX.length));
  }
  return chapterKey(storedKey);
}

export async function getCachedChapter(chapterUrl: string): Promise<string | undefined> {
  return get<string>(chapterKey(chapterUrl));
}

export async function getCachedChapterByIndex(bookUrl: string, chapterIdx: number): Promise<string | undefined> {
  const mappedChapterKey = await get<string>(chapterIdxKey(bookUrl, chapterIdx));
  if (!mappedChapterKey) {
    return undefined;
  }
  return get<string>(normalizeStoredChapterKey(mappedChapterKey));
}

export async function cacheChapter(
  bookUrl: string,
  chapterUrl: string,
  content: string,
  chapterIdx?: number,
): Promise<void> {
  const normalizedChapterKey = chapterKey(chapterUrl);
  await set(normalizedChapterKey, content);

  const idxKey = indexKey(bookUrl);
  const existing = (await get<string[]>(idxKey)) || [];
  if (!existing.includes(normalizedChapterKey)) {
    existing.push(normalizedChapterKey);
    await set(idxKey, existing);
  }

  if (chapterIdx !== undefined) {
    await set(chapterIdxKey(bookUrl, chapterIdx), normalizedChapterKey);
  }
}

export async function cacheChaptersBulk(
  bookUrl: string,
  entries: Array<{ chapterUrl: string; content: string; chapterIdx?: number }>,
): Promise<void> {
  if (entries.length === 0) {
    return;
  }

  const idxKey = indexKey(bookUrl);
  const existing = new Set((await get<string[]>(idxKey)) || []);
  const pairs: [IDBValidKey, unknown][] = [];

  for (const entry of entries) {
    const normalizedChapterKey = chapterKey(entry.chapterUrl);
    pairs.push([normalizedChapterKey, entry.content]);
    existing.add(normalizedChapterKey);
    if (entry.chapterIdx !== undefined) {
      pairs.push([chapterIdxKey(bookUrl, entry.chapterIdx), normalizedChapterKey]);
    }
  }

  pairs.push([idxKey, Array.from(existing)]);
  await setMany(pairs);
}

export async function clearBookChapterCache(bookUrl: string): Promise<number> {
  const idxKey = indexKey(bookUrl);
  const chapterKeys = (await get<string[]>(idxKey)) || [];
  for (const chapterKey of chapterKeys) {
    await del(chapterKey);
  }
  await del(idxKey);

  const idxPrefix = `${BOOK_CHAPTER_IDX_PREFIX}${bookUrl}:`;
  const allKeys = await keys();
  for (const key of allKeys) {
    const keyText = String(key);
    if (keyText.startsWith(idxPrefix)) {
      await del(key);
    }
  }

  return chapterKeys.length;
}

export async function clearAllChapterCache(): Promise<void> {
  await clear();
}

export async function getChapterCacheStats(): Promise<{ chapters: number; books: number }> {
  const allKeys = await keys();
  let rawChapterEntries = 0;
  let mappedChapters = 0;
  let books = 0;
  for (const key of allKeys) {
    const keyText = String(key);
    if (keyText.startsWith(CHAPTER_PREFIX)) rawChapterEntries += 1;
    if (keyText.startsWith(BOOK_CHAPTER_IDX_PREFIX)) mappedChapters += 1;
    if (keyText.startsWith(BOOK_INDEX_PREFIX)) books += 1;
  }
  const chapters = mappedChapters > 0 ? mappedChapters : rawChapterEntries;
  return { chapters, books };
}

export async function getBookChapterCacheCountMap(bookUrls: string[]): Promise<Record<string, number>> {
  const normalizedBookUrls = Array.from(new Set(bookUrls.map((url) => url.trim()).filter(Boolean)));
  const counts: Record<string, number> = {};
  for (const bookUrl of normalizedBookUrls) {
    counts[bookUrl] = 0;
  }

  if (normalizedBookUrls.length === 0) {
    return counts;
  }

  const trackedBooks = new Set(normalizedBookUrls);
  const allKeys = await keys();
  for (const key of allKeys) {
    const keyText = String(key);
    if (!keyText.startsWith(BOOK_CHAPTER_IDX_PREFIX)) {
      continue;
    }

    const suffix = keyText.slice(BOOK_CHAPTER_IDX_PREFIX.length);
    const splitAt = suffix.lastIndexOf(":");
    if (splitAt <= 0) {
      continue;
    }

    const bookUrl = suffix.slice(0, splitAt);
    if (!trackedBooks.has(bookUrl)) {
      continue;
    }

    counts[bookUrl] += 1;
  }

  const fallbackUrls = normalizedBookUrls.filter((bookUrl) => counts[bookUrl] === 0);
  if (fallbackUrls.length > 0) {
    const fallbackPairs = await Promise.all(
      fallbackUrls.map(async (bookUrl) => {
        const indexed = (await get<string[]>(indexKey(bookUrl))) || [];
        return [bookUrl, indexed.length] as const;
      })
    );

    for (const [bookUrl, count] of fallbackPairs) {
      counts[bookUrl] = count;
    }
  }

  return counts;
}

async function getCacheStorageStats(): Promise<{ buckets: number; entries: number }> {
  if (!("caches" in window)) {
    return { buckets: 0, entries: 0 };
  }

  const cacheNames = await window.caches.keys();
  let entries = 0;
  for (const cacheName of cacheNames) {
    const cache = await window.caches.open(cacheName);
    const requests = await cache.keys();
    entries += requests.length;
  }

  return {
    buckets: cacheNames.length,
    entries,
  };
}

async function clearCacheStorage(): Promise<{ bucketsCleared: number }> {
  if (!("caches" in window)) {
    return { bucketsCleared: 0 };
  }

  const cacheNames = await window.caches.keys();
  await Promise.all(cacheNames.map((cacheName) => window.caches.delete(cacheName)));
  return { bucketsCleared: cacheNames.length };
}

export interface BrowserCacheStats {
  chapterBooks: number;
  chapterEntries: number;
  cacheStorageBuckets: number;
  cacheStorageEntries: number;
}

export async function getBrowserCacheStats(): Promise<BrowserCacheStats> {
  const [chapterStats, cacheStorageStats] = await Promise.all([
    getChapterCacheStats(),
    getCacheStorageStats(),
  ]);

  return {
    chapterBooks: chapterStats.books,
    chapterEntries: chapterStats.chapters,
    cacheStorageBuckets: cacheStorageStats.buckets,
    cacheStorageEntries: cacheStorageStats.entries,
  };
}

export interface BrowserCacheClearResult {
  cacheStorageBucketsCleared: number;
}

export async function clearBrowserCache(): Promise<BrowserCacheClearResult> {
  await clearAllChapterCache();
  const storageResult = await clearCacheStorage();
  return {
    cacheStorageBucketsCleared: storageResult.bucketsCleared,
  };
}
