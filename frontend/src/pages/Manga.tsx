import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { SearchResult } from "@/api/client";

interface RankItem {
  name: string;
  book_url: string;
  source_url: string;
}

const MANGA_CATEGORIES = ["全部漫画", "最新更新", "排行榜", "连载漫画", "完结漫画"];

export default function Manga() {
  const [keyword, setKeyword] = useState("");
  const [ranking, setRanking] = useState<RankItem[]>([]);
  const [activeCategory, setActiveCategory] = useState("全部漫画");
  const [rankLoading, setRankLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setRankLoading(true);
    fetch(`/api/explore/manga-ranking?category=${encodeURIComponent(activeCategory)}`)
      .then((r) => r.json())
      .then((d) => { setRanking(d); setRankLoading(false); })
      .catch(() => { setRanking([]); setRankLoading(false); });
  }, [activeCategory]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim()) return;
    setSearching(true);
    setSearchResults([]);

    // Search only tauri/manga sources
    const response = await fetch(
      `/api/search?keyword=${encodeURIComponent(keyword.trim())}&sources=https://m.g-mh.org/`
    );
    if (!response.body) { setSearching(false); return; }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const results: SearchResult[] = [];

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
          results.push(...JSON.parse(payload));
          setSearchResults([...results]);
        } catch {}
      }
    }
    setSearching(false);
  };

  const handleClick = (item: RankItem | SearchResult) => {
    navigate(
      `/book?book_url=${encodeURIComponent(item.book_url)}&source_url=${encodeURIComponent(item.source_url)}`
    );
  };

  return (
    <div>
      {/* Search */}
      <form onSubmit={handleSearch} className="mb-5">
        <div className="flex items-center h-[38px] px-3 rounded-lg bg-black/[0.04] focus-within:bg-black/[0.06] transition-colors">
          <svg className="w-[15px] h-[15px] text-[#86868b] flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.2-5.2m0 0A7.5 7.5 0 105.8 5.8a7.5 7.5 0 0010 10z" />
          </svg>
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索漫画"
            className="flex-1 ml-2 bg-transparent text-[14px] text-[#1d1d1f] placeholder:text-[#86868b]/70 outline-none"
          />
        </div>
      </form>

      {/* Search results */}
      {(searching || searchResults.length > 0) && (
        <section className="mb-6">
          <h2 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wider mb-3">
            搜索结果 {searching && "..."}
          </h2>
          <div>
            {searchResults.map((item, i) => (
              <button
                key={`${item.book_url}-${i}`}
                onClick={() => handleClick(item)}
                className="w-full text-left py-[10px] border-b border-black/[0.04] last:border-0 active:bg-black/[0.02] transition-colors"
              >
                <span className="text-[14px] text-[#1d1d1f] truncate block">{item.name}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Ranking */}
      {!searching && searchResults.length === 0 && (
        <section>
          <h2 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wider mb-3">
            漫画推荐
          </h2>

          {/* Category tabs */}
          <div className="flex gap-1.5 overflow-x-auto scrollbar-none mb-4 -mx-1">
            {MANGA_CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`px-3 py-[5px] text-[12px] font-medium whitespace-nowrap rounded-full transition-all ${
                  activeCategory === cat
                    ? "bg-[#c45d35]/[0.08] text-[#c45d35]"
                    : "bg-black/[0.04] text-[#86868b] hover:text-[#1d1d1f]"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* List */}
          <div className={`transition-opacity duration-200 ${rankLoading ? "opacity-30" : "opacity-100"}`}>
            {ranking.length > 0 ? (
              <div>
                {ranking.map((item, i) => (
                  <button
                    key={item.book_url}
                    onClick={() => handleClick(item)}
                    className="w-full flex items-center py-[10px] border-b border-black/[0.04] last:border-0 text-left active:bg-black/[0.02] transition-colors"
                  >
                    <span className={`w-5 text-[12px] tabular-nums font-bold flex-shrink-0 ${
                      i < 3 ? "text-[#c45d35]" : "text-[#c7c7cc]"
                    }`}>
                      {i + 1}
                    </span>
                    <span className="text-[14px] text-[#1d1d1f] truncate ml-2">
                      {item.name}
                    </span>
                  </button>
                ))}
              </div>
            ) : !rankLoading ? (
              <p className="py-8 text-center text-[13px] text-[#c7c7cc]">暂无数据</p>
            ) : null}
          </div>
        </section>
      )}
    </div>
  );
}
