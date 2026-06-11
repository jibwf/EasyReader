import { useEffect, useMemo, useRef, useState } from "react";
import { api, BookCategoryItem, SourceItem } from "@/api/client";
import { clearBrowserCache, getBrowserCacheStats } from "@/utils/chapter-cache";
import {
  applyFontPreferences,
  FONT_OPTIONS,
  getFontPreferences,
  setFontPreference,
} from "@/utils/font-manager";

const SOURCE_PAGE_SIZE = 20;

export default function Settings() {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourceBusy, setSourceBusy] = useState(false);
  const [sourceMessage, setSourceMessage] = useState("");
  const [sourceUrlInput, setSourceUrlInput] = useState("");
  const [sourcePage, setSourcePage] = useState(1);
  const sourceFileRef = useRef<HTMLInputElement>(null);

  const [categories, setCategories] = useState<BookCategoryItem[]>([]);
  const [categoryBusy, setCategoryBusy] = useState(false);
  const [categoryMessage, setCategoryMessage] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [renameDrafts, setRenameDrafts] = useState<Record<string, string>>({});

  const [serverCacheBusy, setServerCacheBusy] = useState(false);
  const [serverCacheMessage, setServerCacheMessage] = useState("");
  const [serverCacheStats, setServerCacheStats] = useState({
    books: 0,
    chapters: 0,
    bytes: 0,
  });

  const [browserCacheBusy, setBrowserCacheBusy] = useState(false);
  const [browserCacheMessage, setBrowserCacheMessage] = useState("");
  const [browserCacheStats, setBrowserCacheStats] = useState({
    chapterBooks: 0,
    chapterEntries: 0,
    cacheStorageBuckets: 0,
    cacheStorageEntries: 0,
  });

  const [fontPrefs, setFontPrefs] = useState(getFontPreferences());
  const [fontMessage, setFontMessage] = useState("");

  const fontNameMap = useMemo(
    () => new Map(FONT_OPTIONS.map((font) => [font.key, font.name])),
    []
  );

  const sourcePageCount = useMemo(
    () => Math.max(1, Math.ceil(sources.length / SOURCE_PAGE_SIZE)),
    [sources.length]
  );

  const pagedSources = useMemo(() => {
    const start = (sourcePage - 1) * SOURCE_PAGE_SIZE;
    return sources.slice(start, start + SOURCE_PAGE_SIZE);
  }, [sourcePage, sources]);

  useEffect(() => {
    setSourcePage((prev) => Math.min(prev, sourcePageCount));
  }, [sourcePageCount]);

  const loadSources = async () => {
    setSourcesLoading(true);
    try {
      const data = await api.getSources();
      setSources(data);
      setSourcePage((prev) => {
        const maxPage = Math.max(1, Math.ceil(data.length / SOURCE_PAGE_SIZE));
        return Math.min(prev, maxPage);
      });
    } catch {
      setSourceMessage("书源读取失败");
    } finally {
      setSourcesLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const data = await api.getBookCategories();
      setCategories(data);
      setRenameDrafts((prev) => {
        const next: Record<string, string> = {};
        for (const category of data) {
          if (prev[category.name]) {
            next[category.name] = prev[category.name];
          }
        }
        return next;
      });
    } catch {
      setCategoryMessage("分类读取失败");
    }
  };

  const loadServerCacheStats = async () => {
    try {
      const server = await api.getServerCacheStats();
      setServerCacheStats(server);
    } catch {
      setServerCacheMessage("服务器缓存统计读取失败");
    }
  };

  const loadBrowserCacheStats = async () => {
    try {
      const browser = await getBrowserCacheStats();
      setBrowserCacheStats(browser);
    } catch {
      setBrowserCacheMessage("浏览器缓存统计读取失败");
    }
  };

  useEffect(() => {
    loadSources().catch(() => {});
    loadCategories().catch(() => {});
    loadServerCacheStats().catch(() => {});
    loadBrowserCacheStats().catch(() => {});
    setFontPrefs(applyFontPreferences());
  }, []);

  const handleImportSourceFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }

    setSourceBusy(true);
    setSourceMessage("");
    try {
      const parsed = JSON.parse(await file.text());
      const payload = Array.isArray(parsed) ? parsed : [parsed];
      const result = await api.importSources(payload);
      setSourceMessage(`导入 ${result.count} 个书源`);
      await loadSources();
    } catch {
      setSourceMessage("书源文件导入失败");
    } finally {
      setSourceBusy(false);
    }
  };

  const handleImportSourceUrl = async (event: React.FormEvent) => {
    event.preventDefault();
    const url = sourceUrlInput.trim();
    if (!url) {
      setSourceMessage("请输入书源 URL");
      return;
    }

    setSourceBusy(true);
    setSourceMessage("");
    try {
      const result = await api.importSourcesFromUrl(url);
      setSourceUrlInput("");
      setSourceMessage(`导入 ${result.count} 个书源`);
      await loadSources();
    } catch {
      setSourceMessage("书源 URL 导入失败");
    } finally {
      setSourceBusy(false);
    }
  };

  const handleToggleSource = async (sourceUrl: string) => {
    setSourceBusy(true);
    setSourceMessage("");
    try {
      const result = await api.toggleSource(sourceUrl);
      setSourceMessage(result.enabled ? "书源已启用" : "书源已停用");
      await loadSources();
    } catch {
      setSourceMessage("更新书源状态失败");
    } finally {
      setSourceBusy(false);
    }
  };

  const handleDeleteSource = async (source: SourceItem) => {
    const confirmed = window.confirm(`确认删除书源「${source.book_source_name}」吗？`);
    if (!confirmed) {
      return;
    }

    setSourceBusy(true);
    setSourceMessage("");
    try {
      await api.deleteSource(source.book_source_url);
      setSourceMessage(`已删除书源: ${source.book_source_name}`);
      await loadSources();
    } catch {
      setSourceMessage("删除书源失败");
    } finally {
      setSourceBusy(false);
    }
  };

  const handleCreateCategory = async () => {
    const name = newCategoryName.trim();
    if (!name) {
      setCategoryMessage("请输入分类名称");
      return;
    }

    setCategoryBusy(true);
    setCategoryMessage("");
    try {
      await api.createBookCategory(name);
      setNewCategoryName("");
      setCategoryMessage(`已创建分类: ${name}`);
      await loadCategories();
    } catch {
      setCategoryMessage("创建分类失败（可能同名已存在）");
    } finally {
      setCategoryBusy(false);
    }
  };

  const handleToggleCategoryHidden = async (category: BookCategoryItem) => {
    setCategoryBusy(true);
    setCategoryMessage("");
    try {
      await api.setBookCategoryHidden(category.name, !category.hidden);
      setCategoryMessage(category.hidden ? `已取消隐藏: ${category.name}` : `已隐藏: ${category.name}`);
      await loadCategories();
    } catch {
      setCategoryMessage("更新分类隐藏状态失败");
    } finally {
      setCategoryBusy(false);
    }
  };

  const handleRenameCategory = async (oldName: string) => {
    const nextName = (renameDrafts[oldName] || "").trim();
    if (!nextName) {
      setCategoryMessage("请输入新的分类名");
      return;
    }
    if (nextName === oldName) {
      setCategoryMessage("分类名称未变化");
      return;
    }

    setCategoryBusy(true);
    setCategoryMessage("");
    try {
      const result = await api.renameBookCategory(oldName, nextName);
      setRenameDrafts((prev) => {
        const next = { ...prev };
        delete next[oldName];
        return next;
      });
      setCategoryMessage(`分类已重命名: ${result.old_name} -> ${result.new_name}`);
      await loadCategories();
    } catch {
      setCategoryMessage("分类重命名失败");
    } finally {
      setCategoryBusy(false);
    }
  };

  const handleDeleteCategory = async (category: BookCategoryItem) => {
    if (category.preset) {
      setCategoryMessage("预设分类不支持删除");
      return;
    }

    const confirmed = window.confirm(`确认删除分类「${category.name}」吗？分类内书籍将自动转入网文。`);
    if (!confirmed) {
      return;
    }

    setCategoryBusy(true);
    setCategoryMessage("");
    try {
      const result = await api.deleteBookCategory(category.name);
      setCategoryMessage(`已删除分类: ${result.name}，书籍已转入 ${result.reassigned_to}`);
      await loadCategories();
    } catch {
      setCategoryMessage("删除分类失败");
    } finally {
      setCategoryBusy(false);
    }
  };

  const handleClearServerCache = async () => {
    const confirmed = window.confirm("确认清理服务器缓存吗？");
    if (!confirmed) {
      return;
    }

    setServerCacheBusy(true);
    setServerCacheMessage("");
    try {
      const result = await api.clearServerCache({ clear_all: true });
      const latest = await api.getServerCacheStats();
      setServerCacheStats(latest);

      if (latest.chapters === 0) {
        setServerCacheMessage(`服务器缓存已清理（删除 ${result.cleared} 条）`);
      } else {
        setServerCacheMessage(`已执行清理，但仍剩 ${latest.chapters} 章，请稍后再试`);
      }
    } catch {
      setServerCacheMessage("服务器缓存清理失败");
    } finally {
      setServerCacheBusy(false);
    }
  };

  const handleClearBrowserCache = async () => {
    const confirmed = window.confirm("确认清理浏览器缓存吗？这会移除本地章节和离线静态缓存。");
    if (!confirmed) {
      return;
    }

    setBrowserCacheBusy(true);
    setBrowserCacheMessage("");
    try {
      const result = await clearBrowserCache();
      const latest = await getBrowserCacheStats();
      setBrowserCacheStats(latest);

      if (latest.chapterEntries === 0 && latest.cacheStorageEntries === 0) {
        setBrowserCacheMessage(
          `浏览器缓存已清理（清理 Cache Storage ${result.cacheStorageBucketsCleared} 个缓存桶）`
        );
      } else {
        setBrowserCacheMessage(
          `已执行清理，但仍有 ${latest.chapterEntries} 条章节或 ${latest.cacheStorageEntries} 条静态缓存`
        );
      }
    } catch {
      setBrowserCacheMessage("浏览器缓存清理失败");
    } finally {
      setBrowserCacheBusy(false);
    }
  };

  const handleFontChange = (fontKey: string) => {
    const next = setFontPreference(fontKey);
    setFontPrefs(next);
    const fontName = fontNameMap.get(next.fontKey) || next.fontKey;
    setFontMessage(`字体已切换为: ${fontName}（应用与阅读同步）`);
  };

  const renderSourcePager = () => {
    if (sources.length === 0 || sourcePageCount <= 1) {
      return null;
    }

    return (
      <div className="mt-3 flex items-center justify-between gap-2">
        <p className="text-[11px] text-[#86868b]">
          第 {sourcePage} / {sourcePageCount} 页 · 每页 {SOURCE_PAGE_SIZE} 条
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSourcePage((prev) => Math.max(1, prev - 1))}
            disabled={sourcePage <= 1}
            className="px-2 py-1 rounded bg-black/[0.04] text-[11px] text-[#1d1d1f] disabled:opacity-40"
          >
            上一页
          </button>
          <button
            onClick={() => setSourcePage((prev) => Math.min(sourcePageCount, prev + 1))}
            disabled={sourcePage >= sourcePageCount}
            className="px-2 py-1 rounded bg-black/[0.04] text-[11px] text-[#1d1d1f] disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-[860px] mx-auto">
      <h1 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wider mb-4">设置</h1>

      <section className="mb-4 p-3 rounded-xl bg-black/[0.03] border border-black/[0.05]">
        <div className="flex items-center justify-between mb-3 gap-2">
          <h2 className="text-[12px] font-semibold text-[#1d1d1f]">书源管理</h2>
          <span className="text-[11px] text-[#86868b]">{sources.length} 个书源</span>
        </div>

        <form onSubmit={handleImportSourceUrl} className="mb-2">
          <div className="flex items-center h-[38px] px-3 rounded-lg bg-black/[0.04] focus-within:bg-black/[0.06] transition-colors">
            <input
              type="url"
              value={sourceUrlInput}
              onChange={(event) => setSourceUrlInput(event.target.value)}
              placeholder="书源 JSON 地址"
              className="flex-1 bg-transparent text-[13px] text-[#1d1d1f] placeholder:text-[#86868b]/70 outline-none"
              disabled={sourceBusy}
            />
            <button
              type="submit"
              disabled={sourceBusy || !sourceUrlInput.trim()}
              className="text-[12px] font-semibold text-[#c45d35] disabled:opacity-40 ml-2"
            >
              导入
            </button>
          </div>
        </form>

        <div className="flex flex-wrap items-center gap-3 mb-3">
          <label className="text-[12px] text-[#86868b] hover:text-[#1d1d1f] cursor-pointer">
            上传书源文件
            <input
              ref={sourceFileRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleImportSourceFile}
              disabled={sourceBusy}
            />
          </label>
        </div>

        {sourceMessage && <p className="mb-2 text-[12px] text-[#86868b]">{sourceMessage}</p>}

        {sourcesLoading ? (
          <p className="text-[12px] text-[#c7c7cc]">读取中...</p>
        ) : sources.length === 0 ? (
          <p className="text-[12px] text-[#c7c7cc]">暂无书源</p>
        ) : (
          <>
            <div className="space-y-1.5">
              {pagedSources.map((source) => (
                <div
                  key={source.book_source_url}
                  className="flex items-center gap-2 py-1.5 border-b border-black/[0.04] last:border-0"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] text-[#1d1d1f] truncate">{source.book_source_name}</p>
                    <p className="text-[11px] text-[#86868b] truncate">
                      {source.book_source_group || "未分组"} · {source.book_source_type === 2 ? "漫画源" : "小说源"}
                    </p>
                  </div>
                  <button
                    onClick={() => handleToggleSource(source.book_source_url)}
                    disabled={sourceBusy}
                    className={`w-9 h-[22px] rounded-full relative transition-colors duration-200 ${
                      source.enabled ? "bg-[#34c759]" : "bg-black/[0.08]"
                    } disabled:opacity-40`}
                  >
                    <span
                      className={`absolute top-[2px] w-[18px] h-[18px] rounded-full bg-white shadow-sm transition-transform duration-200 ${
                        source.enabled ? "left-[18px]" : "left-[2px]"
                      }`}
                    />
                  </button>
                  <button
                    onClick={() => handleDeleteSource(source)}
                    disabled={sourceBusy}
                    className="px-2 py-1 rounded bg-[#b42318]/10 text-[#b42318] text-[11px] disabled:opacity-40"
                  >
                    删除
                  </button>
                </div>
              ))}
            </div>
            {renderSourcePager()}
          </>
        )}
      </section>

      <section className="mb-4 p-3 rounded-xl bg-black/[0.03] border border-black/[0.05]">
        <h2 className="text-[12px] font-semibold text-[#1d1d1f] mb-3">分类管理</h2>

        <div className="flex flex-wrap gap-2 mb-3">
          <input
            value={newCategoryName}
            onChange={(event) => setNewCategoryName(event.target.value)}
            placeholder="输入新分类名称"
            className="px-2.5 py-1.5 rounded-lg bg-black/[0.04] text-[12px] text-[#1d1d1f] min-w-[180px]"
          />
          <button
            onClick={handleCreateCategory}
            disabled={categoryBusy}
            className="px-2.5 py-1.5 rounded-lg bg-black/[0.06] text-[12px] text-[#1d1d1f] disabled:opacity-50"
          >
            新增分类
          </button>
        </div>

        {categories.length === 0 ? (
          <p className="text-[12px] text-[#c7c7cc]">暂无分类</p>
        ) : (
          <div className="space-y-1.5">
            {categories.map((category) => (
              <div key={category.name} className="flex flex-wrap items-center gap-2 text-[12px]">
                <span className="text-[#1d1d1f]">
                  {category.name}
                  {category.preset ? "（预设）" : ""}
                </span>
                <span className="text-[#86868b]">{category.book_count} 本</span>
                {category.hidden && <span className="text-[#b42318]">已隐藏</span>}
                {!category.preset && (
                  <>
                    <input
                      value={renameDrafts[category.name] || ""}
                      onChange={(event) => {
                        const value = event.target.value;
                        setRenameDrafts((prev) => ({ ...prev, [category.name]: value }));
                      }}
                      placeholder="新分类名"
                      className="px-2 py-1 rounded bg-black/[0.04] text-[12px] text-[#1d1d1f] min-w-[120px]"
                    />
                    <button
                      onClick={() => handleRenameCategory(category.name)}
                      disabled={categoryBusy}
                      className="px-2 py-1 rounded bg-black/[0.06] text-[#1d1d1f] disabled:opacity-50"
                    >
                      重命名
                    </button>
                    <button
                      onClick={() => handleDeleteCategory(category)}
                      disabled={categoryBusy}
                      className="px-2 py-1 rounded bg-[#b42318]/10 text-[#b42318] disabled:opacity-50"
                    >
                      删除
                    </button>
                  </>
                )}
                <button
                  onClick={() => handleToggleCategoryHidden(category)}
                  disabled={categoryBusy}
                  className="ml-auto px-2 py-1 rounded bg-black/[0.06] text-[#1d1d1f] disabled:opacity-50"
                >
                  {category.hidden ? "取消隐藏" : "隐藏"}
                </button>
              </div>
            ))}
          </div>
        )}

        {categoryMessage && <p className="mt-2 text-[12px] text-[#86868b]">{categoryMessage}</p>}
      </section>

      <section className="mb-4 p-3 rounded-xl bg-black/[0.03] border border-black/[0.05]">
        <h2 className="text-[12px] font-semibold text-[#1d1d1f] mb-1">缓存管理</h2>
        <p className="text-[11px] text-[#86868b] mb-3">服务器缓存与浏览器缓存分开管理，互不影响。</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="p-2.5 rounded-lg bg-white border border-black/[0.08]">
            <h3 className="text-[12px] font-semibold text-[#1d1d1f] mb-2">服务器缓存</h3>
            <p className="text-[11px] text-[#86868b]">
              {serverCacheStats.books} 本 / {serverCacheStats.chapters} 章 / {(serverCacheStats.bytes / 1024 / 1024).toFixed(2)} MB
            </p>
            <div className="flex items-center gap-2 mt-2">
              <button
                onClick={() => loadServerCacheStats().catch(() => {})}
                disabled={serverCacheBusy}
                className="px-2 py-1 rounded bg-black/[0.04] text-[11px] text-[#1d1d1f] disabled:opacity-40"
              >
                刷新统计
              </button>
              <button
                onClick={handleClearServerCache}
                disabled={serverCacheBusy}
                className="px-2 py-1 rounded bg-black/[0.06] text-[11px] text-[#1d1d1f] disabled:opacity-40"
              >
                清理服务器缓存
              </button>
            </div>
            {serverCacheMessage && <p className="mt-2 text-[11px] text-[#86868b]">{serverCacheMessage}</p>}
          </div>

          <div className="p-2.5 rounded-lg bg-white border border-black/[0.08]">
            <h3 className="text-[12px] font-semibold text-[#1d1d1f] mb-2">浏览器缓存</h3>
            <p className="text-[11px] text-[#86868b]">
              章节缓存: {browserCacheStats.chapterBooks} 本 / {browserCacheStats.chapterEntries} 章
            </p>
            <p className="text-[11px] text-[#86868b]">
              静态缓存: {browserCacheStats.cacheStorageBuckets} 个桶 / {browserCacheStats.cacheStorageEntries} 条
            </p>
            <div className="flex items-center gap-2 mt-2">
              <button
                onClick={() => loadBrowserCacheStats().catch(() => {})}
                disabled={browserCacheBusy}
                className="px-2 py-1 rounded bg-black/[0.04] text-[11px] text-[#1d1d1f] disabled:opacity-40"
              >
                刷新统计
              </button>
              <button
                onClick={handleClearBrowserCache}
                disabled={browserCacheBusy}
                className="px-2 py-1 rounded bg-black/[0.06] text-[11px] text-[#1d1d1f] disabled:opacity-40"
              >
                清理浏览器缓存
              </button>
            </div>
            {browserCacheMessage && <p className="mt-2 text-[11px] text-[#86868b]">{browserCacheMessage}</p>}
          </div>
        </div>
      </section>

      <section className="mb-4 p-3 rounded-xl bg-black/[0.03] border border-black/[0.05]">
        <h2 className="text-[12px] font-semibold text-[#1d1d1f] mb-1">字体管理</h2>
        <p className="text-[11px] text-[#86868b] mb-3">
          应用界面与阅读正文使用同一套字体。已内置 5 款免费字体并提供系统默认回退。
        </p>

        <div className="space-y-1.5">
          {FONT_OPTIONS.map((font) => (
            <button
              key={font.key}
              onClick={() => handleFontChange(font.key)}
              className={`w-full text-left p-2 rounded-lg border transition-colors ${
                fontPrefs.fontKey === font.key
                  ? "border-[#c45d35] bg-[#c45d35]/[0.06]"
                  : "border-black/[0.08] bg-white"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[12px] text-[#1d1d1f]" style={{ fontFamily: font.family }}>
                  {font.name}
                </span>
                <span className="text-[10px] text-[#86868b]">{font.license}</span>
              </div>
              <p className="text-[11px] text-[#86868b] mt-0.5">{font.description}</p>
              <p className="text-[10px] text-[#86868b] mt-0.5">来源: {font.source}</p>
              <p className="text-[12px] mt-1 text-[#1d1d1f]" style={{ fontFamily: font.family }}>
                墨水屏预览：山不在高，有仙则名；水不在深，有龙则灵。
              </p>
            </button>
          ))}
        </div>

        {fontMessage && <p className="mt-2 text-[12px] text-[#86868b]">{fontMessage}</p>}
      </section>
    </div>
  );
}
