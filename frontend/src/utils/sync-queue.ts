import { SyncProgressPayload } from "@/api/client";

const PROGRESS_QUEUE_KEY = "sync_progress_queue_v1";
const MAX_QUEUE_ITEMS = 200;

type QueuedProgressItem = SyncProgressPayload & {
  queued_at: number;
};

function readQueue(): QueuedProgressItem[] {
  try {
    const raw = localStorage.getItem(PROGRESS_QUEUE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as QueuedProgressItem[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item) => typeof item?.book_key === "string" && item.book_key.length > 0
    );
  } catch {
    return [];
  }
}

function dedupeAndLimit(items: QueuedProgressItem[]): QueuedProgressItem[] {
  const byBook = new Map<string, QueuedProgressItem>();
  for (const item of items) {
    const key = `${item.user_id}::${item.book_key}`;
    byBook.set(key, item);
  }
  return [...byBook.values()]
    .sort((a, b) => a.queued_at - b.queued_at)
    .slice(-MAX_QUEUE_ITEMS);
}

function writeQueue(items: QueuedProgressItem[]): void {
  try {
    const normalized = dedupeAndLimit(items);
    localStorage.setItem(PROGRESS_QUEUE_KEY, JSON.stringify(normalized));
  } catch {
    // Ignore quota/private-mode errors.
  }
}

export function enqueueSyncProgress(payload: SyncProgressPayload): void {
  if (!payload.book_key) {
    return;
  }
  const queue = readQueue();
  queue.push({ ...payload, queued_at: Date.now() });
  writeQueue(queue);
}

export function getSyncProgressQueueSize(): number {
  return readQueue().length;
}

export function clearSyncProgressQueue(): void {
  try {
    localStorage.removeItem(PROGRESS_QUEUE_KEY);
  } catch {
    // Ignore storage errors.
  }
}

export async function flushSyncProgressQueue(
  send: (payload: SyncProgressPayload) => Promise<unknown>
): Promise<number> {
  const queue = readQueue();
  if (queue.length === 0) return 0;

  const failed: QueuedProgressItem[] = [];
  let flushedCount = 0;

  for (const entry of queue) {
    const { queued_at: _queuedAt, ...payload } = entry;
    try {
      await send(payload);
      flushedCount += 1;
    } catch {
      failed.push(entry);
    }
  }

  writeQueue(failed);
  return flushedCount;
}
