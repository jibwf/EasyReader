import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, SyncProgressItem } from "@/api/client";
import { getClientIdentity } from "@/utils/client-identity";

interface RankItem {
  book_key: string;
  name: string;
  book_url: string;
  source_url: string;
}

const CATEGORIES = [
  { key: "xuanhuan", label: "玄幻" },
  { key: "dushi", label: "都市" },
  { key: "xianxia", label: "仙侠" },
  { key: "yanqing", label: "言情" },
  { key: "kehuan", label: "科幻" },
  { key: "lishi", label: "历史" },
  { key: "wuxia", label: "武侠" },
];

const PERIODS = [
  { key: "week", label: "周排行" },
  { key: "month", label: "月排行" },
  { key: "all", label: "总排行" },
];

const CONTINUE_LIMIT = 8;

export default function Home() {
  const [keyword, setKeyword] = useState("");
  const [progress, setProgress] = useState<SyncProgressItem[]>([]);
  const [ranking, setRanking] = useState<RankItem[]>([]);
  const [activeCategory, setActiveCategory] = useState("xuanhuan");
  const [activePeriod, setActivePeriod] = useState("week");
  const [rankLoading, setRankLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const identity = getClientIdentity();
    Promise.all([api.pullSyncProgress(identity.userId, 0, 200), api.getBooks()])
      .then(([syncData, visibleBooks]) => {
        const visibleBookKeys = new Set(visibleBooks.map((book) => book.book_key));
        const latestByBook = new Map<string, SyncProgressItem>();
        const sorted = [...syncData.items].sort((a, b) => b.revision - a.revision);

        for (const item of sorted) {
          if (!visibleBookKeys.has(item.book_key)) continue;
          if (!latestByBook.has(item.book_key)) {
            latestByBook.set(item.book_key, item);
          }
        }

        setProgress([...latestByBook.values()]);
      })
      .catch(() => {
        // Avoid leaking hidden entries when visibility lookup fails.
        setProgress([]);
      });
  }, []);

  useEffect(() => {
    setRankLoading(true);
    fetch(`/api/explore/ranking?category=${activeCategory}&period=${activePeriod}`)
      .then((r) => r.json())
      .then((d) => { setRanking(d); setRankLoading(false); })
      .catch(() => { setRanking([]); setRankLoading(false); });
  }, [activeCategory, activePeriod]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (keyword.trim()) navigate(`/search?keyword=${encodeURIComponent(keyword.trim())}`);
  };

  const handleContinue = (item: SyncProgressItem) => {
    navigate(`/read?url=${encodeURIComponent(item.chapter_url)}&source_url=${encodeURIComponent(item.source_url)}&title=${encodeURIComponent(item.chapter_title)}&idx=${item.chapter_idx}&book_key=${encodeURIComponent(item.book_key)}&book_url=${encodeURIComponent(item.book_url)}&book_name=${encodeURIComponent(item.book_name)}`);
  };

  const handleRankClick = (item: RankItem) => {
    navigate(`/book?book_url=${encodeURIComponent(item.book_url)}&source_url=${encodeURIComponent(item.source_url)}&book_key=${encodeURIComponent(item.book_key)}`);
  };

  return (
    <div>
      {/* Search */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex items-center h-[38px] px-3 rounded-lg bg-black/[0.04] transition-colors focus-within:bg-black/[0.06]">
          <svg className="w-[15px] h-[15px] text-[#86868b] flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.2-5.2m0 0A7.5 7.5 0 105.8 5.8a7.5 7.5 0 0010 10z" />
          </svg>
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索书名或作者"
            className="flex-1 ml-2 bg-transparent text-[14px] text-[#1d1d1f] placeholder:text-[#86868b]/70 outline-none"
          />
        </div>
      </form>

      {/* Desktop: two-column layout */}
      <div className="md:grid md:grid-cols-[1fr_1.2fr] md:gap-10">
        {/* Left column: 继续阅读 */}
        <div>
          {progress.length > 0 && (
            <section className="mb-8 md:mb-0">
              <h2 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wider mb-3">
                继续阅读
              </h2>
              <div className="space-y-2">
                {progress.slice(0, CONTINUE_LIMIT).map((item) => (
                  <button
                    key={item.book_key}
                    onClick={() => handleContinue(item)}
                    className="w-full text-left p-3.5 rounded-xl bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06),0_1px_2px_rgba(0,0,0,0.04)] active:scale-[0.98] transition-transform duration-150"
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-[15px] font-medium text-[#1d1d1f] truncate">
                          {item.book_name}
                        </p>
                        <p className="text-[12px] text-[#86868b] mt-1 truncate">
                          {item.chapter_title}
                        </p>
                      </div>
                      <div className="flex-shrink-0 w-[3px] h-9 rounded-full bg-black/[0.04] overflow-hidden">
                        <div
                          className="w-full bg-[#c45d35] rounded-full transition-all"
                          style={{ height: `${Math.min(95, (item.chapter_idx + 1) * 4)}%` }}
                        />
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* Empty state for desktop left column when no progress */}
          {progress.length === 0 && (
            <div className="hidden md:block">
              <h2 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wider mb-3">
                继续阅读
              </h2>
              <div className="py-8 text-center text-[13px] text-[#c7c7cc]">
                阅读记录将显示在此处
              </div>
            </div>
          )}
        </div>

        {/* Right column: 发现 */}
        <section>
          <h2 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wider mb-3">
            发现
          </h2>

          {/* Period tabs */}
          <div className="flex items-center gap-1.5 mb-3">
            {PERIODS.map((p) => (
              <button
                key={p.key}
                onClick={() => setActivePeriod(p.key)}
                className={`px-3 py-[5px] rounded-full text-[12px] font-medium transition-all duration-200 ${
                  activePeriod === p.key
                    ? "bg-[#1d1d1f] text-white"
                    : "bg-black/[0.04] text-[#86868b] hover:text-[#1d1d1f]"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Category tabs */}
          <div className="flex gap-0 overflow-x-auto scrollbar-none pb-3 -mx-1">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.key}
                onClick={() => setActiveCategory(cat.key)}
                className={`px-3 py-[5px] text-[13px] font-medium whitespace-nowrap transition-all duration-200 rounded-md ${
                  activeCategory === cat.key
                    ? "text-[#c45d35] bg-[#c45d35]/[0.06]"
                    : "text-[#86868b] hover:text-[#1d1d1f]"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Ranking list */}
          <div className={`transition-opacity duration-200 ${rankLoading ? "opacity-30" : "opacity-100"}`}>
            {ranking.length > 0 ? (
              <div>
                {ranking.map((item, i) => (
                  <button
                    key={item.book_url}
                    onClick={() => handleRankClick(item)}
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
              <div className="py-8 text-center text-[13px] text-[#c7c7cc]">暂无数据</div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}
