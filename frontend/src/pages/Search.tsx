import { useEffect, useState, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useBookStore } from "@/stores/bookStore";
import { api, SearchResult } from "@/api/client";

export default function Search() {
  const [params] = useSearchParams();
  const keyword = params.get("keyword") || "";
  const { searchResults, searchKeyword, loading, search, searchMode, fullSearchRunning, fullSearchDone } = useBookStore();
  const navigate = useNavigate();
  const [sourceFilter, setSourceFilter] = useState("");
  const [showOther, setShowOther] = useState(false);
  const [shelfBookKeys, setShelfBookKeys] = useState<Set<string>>(new Set());
  const [addingBookKeys, setAddingBookKeys] = useState<Set<string>>(new Set());
  const [statusMessage, setStatusMessage] = useState("");

  useEffect(() => {
    if (keyword) {
      void search(keyword, { mode: "fast", append: false });
    }
  }, [keyword, search]);

  useEffect(() => {
    api.getBooks()
      .then((books) => {
        setShelfBookKeys(new Set(books.map((book) => book.book_key.toLowerCase()).filter(Boolean)));
      })
      .catch(() => {
        setShelfBookKeys(new Set());
      });
  }, []);

  const triggerFullSearch = () => {
    if (!keyword || fullSearchRunning) return;
    void search(keyword, { mode: "full", append: true });
  };

  const sources = useMemo(() => {
    const s = new Set(searchResults.map((r) => r.source_name).filter(Boolean));
    return Array.from(s).sort();
  }, [searchResults]);

  const { matched, other } = useMemo(() => {
    const kw = (searchKeyword || keyword).toLowerCase();
    let filtered = searchResults;
    if (sourceFilter) {
      filtered = filtered.filter((r) => r.source_name === sourceFilter);
    }
    const matched = filtered.filter(
      (r) => r.name.toLowerCase().includes(kw) || r.author.toLowerCase().includes(kw)
    );
    const other = filtered.filter(
      (r) => !r.name.toLowerCase().includes(kw) && !r.author.toLowerCase().includes(kw)
    );
    return { matched, other };
  }, [searchResults, sourceFilter, searchKeyword, keyword]);

  const handleBookClick = (bookUrl: string, sourceUrl: string, bookKey: string) => {
    navigate(`/book?book_url=${encodeURIComponent(bookUrl)}&source_url=${encodeURIComponent(sourceUrl)}&book_key=${encodeURIComponent(bookKey)}`);
  };

  const toResultKey = (item: SearchResult) => {
    if (item.book_key) {
      return item.book_key.toLowerCase();
    }
    return `${item.source_url}::${item.book_url}`.toLowerCase();
  };

  const handleAddToShelf = async (event: React.MouseEvent, item: SearchResult) => {
    event.stopPropagation();
    const resultKey = toResultKey(item);
    if (shelfBookKeys.has(resultKey) || addingBookKeys.has(resultKey)) {
      return;
    }

    setAddingBookKeys((prev) => {
      const next = new Set(prev);
      next.add(resultKey);
      return next;
    });
    setStatusMessage("");

    try {
      await api.addBook({
        book_key: item.book_key,
        name: item.name,
        author: item.author,
        cover_url: item.cover_url,
        intro: item.intro,
        book_url: item.book_url,
        source_url: item.source_url,
      });
      setShelfBookKeys((prev) => {
        const next = new Set(prev);
        next.add(resultKey);
        return next;
      });
      setStatusMessage(`已加入书架：${item.name}`);
    } catch {
      setStatusMessage(`加入书架失败：${item.name}`);
    } finally {
      setAddingBookKeys((prev) => {
        const next = new Set(prev);
        next.delete(resultKey);
        return next;
      });
    }
  };

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-[17px] font-bold text-[#1d1d1f]">{keyword}</h1>
        <p className="text-[12px] text-[#86868b] mt-1">
          {loading
            ? `${searchMode === "full" ? "完整搜索中" : "快速搜索中"} · ${searchResults.length} 条`
            : `${matched.length} 个结果${other.length ? ` · ${other.length} 个其他` : ""}`}
        </p>
        {statusMessage && <p className="text-[12px] text-[#86868b] mt-1">{statusMessage}</p>}
        {keyword && (
          <div className="mt-2 flex items-center gap-2">
            <button
              onClick={() => void search(keyword, { mode: "fast", append: false })}
              className={`px-2.5 py-1 text-[11px] font-medium rounded-full transition-all ${
                searchMode === "fast" && !fullSearchDone ? "bg-[#1d1d1f] text-white" : "bg-black/[0.04] text-[#86868b]"
              }`}
            >
              快速
            </button>
            <button
              onClick={triggerFullSearch}
              disabled={fullSearchRunning}
              className={`px-2.5 py-1 text-[11px] font-medium rounded-full transition-all ${
                fullSearchRunning ? "bg-black/[0.08] text-[#b0b0b5]" : "bg-black/[0.04] text-[#4b4b50]"
              }`}
            >
              {fullSearchRunning ? "完整搜索中" : fullSearchDone ? "完整已完成" : "继续完整"}
            </button>
          </div>
        )}
      </div>

      {/* Filter bar */}
      {sources.length > 1 && (
        <div className="flex gap-1.5 overflow-x-auto scrollbar-none mb-4 -mx-1 pb-1">
          <button
            onClick={() => setSourceFilter("")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded-full whitespace-nowrap transition-all ${
              !sourceFilter ? "bg-[#1d1d1f] text-white" : "bg-black/[0.04] text-[#86868b]"
            }`}
          >
            全部
          </button>
          {sources.map((s) => (
            <button
              key={s}
              onClick={() => setSourceFilter(s === sourceFilter ? "" : s)}
              className={`px-2.5 py-1 text-[11px] font-medium rounded-full whitespace-nowrap transition-all ${
                sourceFilter === s ? "bg-[#1d1d1f] text-white" : "bg-black/[0.04] text-[#86868b]"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Matched results */}
      <div className="grid grid-cols-1 md:grid-cols-2 md:gap-x-6">
        {matched.map((item, i) => (
          <div
            key={`${item.book_url}-${i}`}
            className="flex items-center gap-2 py-3 border-b border-black/[0.04]"
          >
            <button
              onClick={() => handleBookClick(item.book_url, item.source_url, item.book_key)}
              className="flex-1 min-w-0 text-left active:bg-black/[0.02] transition-colors"
            >
              <p className="text-[14px] text-[#1d1d1f] truncate">{item.name}</p>
              <p className="text-[12px] text-[#86868b] mt-0.5 truncate">
                {item.author}
                {item.source_name && <span className="text-[#c7c7cc]"> · {item.source_name}</span>}
              </p>
            </button>
            <button
              onClick={(event) => void handleAddToShelf(event, item)}
              disabled={shelfBookKeys.has(toResultKey(item)) || addingBookKeys.has(toResultKey(item))}
              className="px-2.5 py-1 rounded-lg bg-black/[0.05] text-[11px] text-[#1d1d1f] disabled:opacity-40"
            >
              {shelfBookKeys.has(toResultKey(item))
                ? "已在书架"
                : addingBookKeys.has(toResultKey(item))
                ? "加入中..."
                : "加入书架"}
            </button>
          </div>
        ))}
      </div>

      {/* Other results (collapsed) */}
      {other.length > 0 && (
        <div className="mt-4">
          <button
            onClick={() => setShowOther(!showOther)}
            className="text-[12px] text-[#86868b] hover:text-[#1d1d1f] transition-colors"
          >
            {showOther ? "收起" : "展开"} 其他结果 ({other.length})
          </button>
          {showOther && (
            <div className="mt-2 grid grid-cols-1 md:grid-cols-2 md:gap-x-6 opacity-60">
              {other.map((item, i) => (
                <div
                  key={`other-${item.book_url}-${i}`}
                  className="flex items-center gap-2 py-2.5 border-b border-black/[0.04]"
                >
                  <button
                    onClick={() => handleBookClick(item.book_url, item.source_url, item.book_key)}
                    className="flex-1 min-w-0 text-left active:bg-black/[0.02] transition-colors"
                  >
                    <p className="text-[13px] text-[#1d1d1f] truncate">{item.name}</p>
                    <p className="text-[11px] text-[#c7c7cc] mt-0.5 truncate">
                      {item.author} · {item.source_name}
                    </p>
                  </button>
                  <button
                    onClick={(event) => void handleAddToShelf(event, item)}
                    disabled={shelfBookKeys.has(toResultKey(item)) || addingBookKeys.has(toResultKey(item))}
                    className="px-2 py-1 rounded-lg bg-black/[0.05] text-[10px] text-[#1d1d1f] disabled:opacity-40"
                  >
                    {shelfBookKeys.has(toResultKey(item))
                      ? "已在书架"
                      : addingBookKeys.has(toResultKey(item))
                      ? "加入中"
                      : "加入"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!loading && matched.length === 0 && other.length === 0 && keyword && (
        <p className="text-[13px] text-[#c7c7cc] text-center pt-16">未找到相关书籍</p>
      )}
    </div>
  );
}
