import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, BookItem, OfflineCatalogItem, OfflineTaskItem } from "@/api/client";
import { getClientIdentity } from "@/utils/client-identity";
import {
  loadBooksCache,
  saveBooksCache,
  loadOfflineCatalogCache,
  saveOfflineCatalogCache,
  loadOfflineTasksCache,
  saveOfflineTasksCache,
} from "@/utils/local-cache";

type RowStatus = "completed" | "failed" | "pending" | "not_downloaded";

interface OfflineRow {
  book: BookItem;
  status: RowStatus;
  cached: number;
  total: number;
  updatedAt: string;
  errorMessage: string;
}

function formatTime(value: string): string {
  if (!value) return "-";
  const date = new Date(value.replace(" ", "T") + "Z");
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function OfflineCatalog() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [busyMap, setBusyMap] = useState<Record<number, boolean>>({});
  const [statusText, setStatusText] = useState("");
  const [books, setBooks] = useState<BookItem[]>(() => loadBooksCache<BookItem>());
  const [catalog, setCatalog] = useState<OfflineCatalogItem[]>(() => loadOfflineCatalogCache<OfflineCatalogItem>());
  const [tasks, setTasks] = useState<OfflineTaskItem[]>(() => loadOfflineTasksCache<OfflineTaskItem>());

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const identity = getClientIdentity();
      const [bookList, catalogList, taskList] = await Promise.all([
        api.getBooks(),
        api.getOfflineCatalog(identity.userId, identity.deviceId),
        api.getOfflineTasks(identity.userId, identity.deviceId, 200),
      ]);
      setBooks(bookList);
      setCatalog(catalogList);
      setTasks(taskList);
      saveBooksCache(bookList);
      saveOfflineCatalogCache(catalogList);
      saveOfflineTasksCache(taskList);
      setStatusText(`已刷新 ${bookList.length} 本书的离线状态`);
    } catch {
      // Network failed — keep whatever seeds came from localStorage
      const cachedBooks = loadBooksCache<BookItem>();
      const cachedCatalog = loadOfflineCatalogCache<OfflineCatalogItem>();
      const cachedTasks = loadOfflineTasksCache<OfflineTaskItem>();
      if (cachedBooks.length > 0) {
        setBooks(cachedBooks);
        setCatalog(cachedCatalog);
        setTasks(cachedTasks);
        setStatusText("离线模式：显示本地缓存离线目录。");
      } else {
        setStatusText("离线模式：暂无缓存数据，联网后重新打开可获取离线目录。");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData().catch(() => {});
  }, [fetchData]);

  const latestTaskByBook = useMemo(() => {
    const map = new Map<number, OfflineTaskItem>();
    for (const task of tasks) {
      if (!map.has(task.book_id)) map.set(task.book_id, task);
    }
    return map;
  }, [tasks]);

  const catalogByBook = useMemo(() => {
    const map = new Map<number, OfflineCatalogItem>();
    for (const item of catalog) map.set(item.book_id, item);
    return map;
  }, [catalog]);

  const rows: OfflineRow[] = useMemo(
    () =>
      books.map((book) => {
        const cat = catalogByBook.get(book.id);
        const task = latestTaskByBook.get(book.id);
        if (cat) {
          return {
            book,
            status: "completed",
            cached: cat.cached_chapters,
            total: cat.total_chapters,
            updatedAt: cat.updated_at,
            errorMessage: "",
          };
        }

        if (task?.status === "failed") {
          return {
            book,
            status: "failed",
            cached: task.cached_chapters,
            total: task.total_chapters,
            updatedAt: task.updated_at,
            errorMessage: task.error_message || "离线下载失败",
          };
        }

        if (task?.status === "queued" || task?.status === "running") {
          return {
            book,
            status: "pending",
            cached: task.cached_chapters,
            total: task.total_chapters,
            updatedAt: task.updated_at,
            errorMessage: "",
          };
        }

        return {
          book,
          status: "not_downloaded",
          cached: 0,
          total: book.total_chapters,
          updatedAt: "",
          errorMessage: "",
        };
      }),
    [books, catalogByBook, latestTaskByBook]
  );

  const failedRows = useMemo(() => rows.filter((row) => row.status === "failed"), [rows]);

  const retryOne = async (bookId: number) => {
    const identity = getClientIdentity();
    setBusyMap((prev) => ({ ...prev, [bookId]: true }));
    try {
      await api.createOfflineTask({
        user_id: identity.userId,
        device_id: identity.deviceId,
        book_id: bookId,
      });
      setStatusText("已触发重试任务");
      await fetchData();
    } catch {
      setStatusText("重试失败，请稍后再试");
    } finally {
      setBusyMap((prev) => ({ ...prev, [bookId]: false }));
    }
  };

  const retryFailed = async () => {
    if (failedRows.length === 0) {
      setStatusText("当前没有失败任务");
      return;
    }
    const identity = getClientIdentity();
    setStatusText(`正在重试 ${failedRows.length} 本...`);
    for (const row of failedRows) {
      setBusyMap((prev) => ({ ...prev, [row.book.id]: true }));
      try {
        await api.createOfflineTask({
          user_id: identity.userId,
          device_id: identity.deviceId,
          book_id: row.book.id,
        });
      } catch {
        // Continue retrying remaining books even if one fails.
      } finally {
        setBusyMap((prev) => ({ ...prev, [row.book.id]: false }));
      }
    }
    await fetchData();
  };

  if (loading) {
    return <div className="pt-12 text-center text-[13px] text-[#86868b]">离线目录加载中...</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h1 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wider">离线目录</h1>
          <p className="text-[12px] text-[#86868b] mt-1">可查看每本书离线状态，失败后可重试。</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => fetchData().catch(() => {})}
            className="px-2.5 py-1.5 rounded-lg bg-black/[0.06] text-[12px] text-[#1d1d1f]"
          >
            一键刷新
          </button>
          <button
            onClick={retryFailed}
            className="px-2.5 py-1.5 rounded-lg bg-[#c45d35]/10 text-[12px] text-[#c45d35]"
          >
            重试失败
          </button>
          <button
            onClick={() => navigate("/shelf")}
            className="px-2.5 py-1.5 rounded-lg bg-black/[0.04] text-[12px] text-[#86868b]"
          >
            返回书架
          </button>
        </div>
      </div>

      {statusText && <p className="text-[12px] text-[#86868b] mb-3">{statusText}</p>}

      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.book.id} className="p-3 rounded-xl bg-white border border-black/[0.05]">
            <div className="flex items-start gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-[14px] text-[#1d1d1f] font-medium truncate">{row.book.name}</p>
                <p className="text-[12px] text-[#86868b] mt-1">
                  {row.status === "completed" && `已离线 ${row.cached}/${row.total} 章`}
                  {row.status === "failed" && `失败 ${row.cached}/${row.total} 章`}
                  {row.status === "pending" && `进行中 ${row.cached}/${row.total} 章`}
                  {row.status === "not_downloaded" && "未加入离线目录"}
                </p>
                <p className="text-[11px] text-[#c7c7cc] mt-1">更新时间: {formatTime(row.updatedAt)}</p>
                {row.errorMessage && (
                  <p className="text-[11px] text-[#b42318] mt-1 truncate">{row.errorMessage}</p>
                )}
              </div>

              <div className="flex gap-2">
                {row.status === "failed" && (
                  <button
                    disabled={Boolean(busyMap[row.book.id])}
                    onClick={() => retryOne(row.book.id)}
                    className="px-2.5 py-1.5 rounded-lg bg-[#c45d35]/10 text-[12px] text-[#c45d35] disabled:opacity-50"
                  >
                    重试
                  </button>
                )}
                {(row.status === "not_downloaded" || row.status === "completed") && (
                  <button
                    disabled={Boolean(busyMap[row.book.id])}
                    onClick={() => retryOne(row.book.id)}
                    className="px-2.5 py-1.5 rounded-lg bg-[#0a66c2]/10 text-[12px] text-[#0a66c2] disabled:opacity-50"
                  >
                    {row.status === "completed" ? "刷新本书" : "开始离线"}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
