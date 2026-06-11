import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, BookInfo, Chapter } from "@/api/client";
import { loadChaptersCache, saveChaptersCache } from "@/utils/local-cache";

export default function BookDetail() {
  const [params] = useSearchParams();
  const bookKey = params.get("book_key") || "";
  const bookUrl = params.get("book_url") || "";
  const sourceUrl = params.get("source_url") || "";
  const fallbackName = params.get("name") || "";
  const navigate = useNavigate();

  const [info, setInfo] = useState<BookInfo | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [added, setAdded] = useState(false);
  const [adding, setAdding] = useState(false);
  const [addMessage, setAddMessage] = useState("");

  useEffect(() => {
    if (!bookKey && (!bookUrl || !sourceUrl)) return;
    setLoading(true);

    const identity = {
      bookKey,
      bookUrl,
      sourceUrl,
    };

    Promise.all([
      api.getBookInfo(identity).catch(() => null),
      api.getChapters(identity)
        .then((list) => { saveChaptersCache(bookUrl, list); return list; })
        .catch(() => loadChaptersCache<Chapter>(bookUrl)),
    ]).then(([bookInfo, chapterList]) => {
      setInfo(bookInfo);
      setChapters(chapterList);
      setLoading(false);
    });
  }, [bookKey, bookUrl, sourceUrl]);

  const handleChapterClick = (chapter: Chapter) => {
    navigate(
      `/read?url=${encodeURIComponent(chapter.url)}&source_url=${encodeURIComponent(sourceUrl)}&title=${encodeURIComponent(chapter.title)}&idx=${chapter.idx}&book_url=${encodeURIComponent(bookUrl)}&book_name=${encodeURIComponent(info?.name || fallbackName || "")}&book_key=${encodeURIComponent(bookKey)}`
    );
  };

  const handleAddToShelf = async () => {
    if (added || adding) {
      return;
    }

    setAdding(true);
    setAddMessage("");
    try {
      await api.addBook({
        book_key: bookKey,
        name: info?.name || fallbackName || "未命名书籍",
        author: info?.author || "",
        cover_url: info?.cover_url || "",
        intro: info?.intro || "",
        book_url: bookUrl,
        source_url: sourceUrl,
        total_chapters: chapters.length,
      });
      setAdded(true);
      setAddMessage("已加入书架");
    } catch {
      setAddMessage("加入书架失败");
    } finally {
      setAdding(false);
    }
  };

  if (!bookKey && (!bookUrl || !sourceUrl)) {
    return <div className="pt-12 text-center text-[13px] text-[#c7c7cc]">缺少书籍参数</div>;
  }

  if (loading) return <div className="pt-12 text-center text-[13px] text-[#c7c7cc]">加载中</div>;

  const displayName = info?.name || fallbackName || "未命名书籍";

  return (
    <div className="md:grid md:grid-cols-[2fr_3fr] md:gap-10">
      {/* Left: Book info */}
      {(info || fallbackName) && (
        <div className="mb-8 md:mb-0 md:sticky md:top-24 md:self-start">
          <button onClick={() => navigate(-1)} className="text-[13px] text-[#86868b] mb-4 hover:text-[#1d1d1f] transition-colors">
            ← 返回
          </button>
          <h1 className="text-[20px] font-bold text-[#1d1d1f] leading-tight">
            {displayName}
          </h1>
          {info?.author && (
            <p className="text-[14px] text-[#86868b] mt-1.5">{info.author}</p>
          )}
          {info?.intro && (
            <p className="text-[13px] text-[#86868b] mt-4 leading-[1.7] line-clamp-4 md:line-clamp-none">
              {info.intro}
            </p>
          )}
          <div className="flex items-center gap-4 mt-5">
            <button
              onClick={handleAddToShelf}
              disabled={added || adding}
              className={`px-4 py-2 rounded-lg text-[13px] font-medium transition-all duration-200 active:scale-[0.96] ${
                added
                  ? "bg-[#34c759]/10 text-[#34c759]"
                  : "bg-[#c45d35] text-white hover:bg-[#b05230]"
              }`}
            >
              {added ? "已加入" : adding ? "加入中..." : "加入书架"}
            </button>
            <span className="text-[12px] text-[#c7c7cc]">{chapters.length} 章</span>
          </div>
          {addMessage && <p className="text-[12px] text-[#86868b] mt-2">{addMessage}</p>}
        </div>
      )}

      {/* Right: Chapter list */}
      <section>
        <h2 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wider mb-3 md:mt-0 mt-2">
          目录
        </h2>
        <div className="md:max-h-[70vh] md:overflow-y-auto md:pr-2">
          {chapters.length === 0 && (
            <p className="text-[13px] text-[#c7c7cc] py-4">暂未获取到目录，可先加入书架后再试。</p>
          )}
          {chapters.map((ch) => (
            <button
              key={ch.idx}
              onClick={() => handleChapterClick(ch)}
              className="w-full text-left py-[10px] border-b border-black/[0.04] last:border-0 text-[14px] text-[#1d1d1f] truncate active:bg-black/[0.02] hover:text-[#c45d35] transition-colors"
            >
              {ch.title}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
