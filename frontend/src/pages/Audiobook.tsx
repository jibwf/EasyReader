import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api, type AudiobookItem } from "@/api/client";

export default function Audiobook() {
  const [books, setBooks] = useState<AudiobookItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [status, setStatus] = useState("");
  const [scanLogs, setScanLogs] = useState<string[]>([]);
  const [coverModal, setCoverModal] = useState<{ book: AudiobookItem; url: string } | null>(null);
  const [settingCover, setSettingCover] = useState(false);
  const [deleteModal, setDeleteModal] = useState<AudiobookItem | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const loadBooks = async () => {
    setLoading(true);
    try {
      const list = await api.getAudiobookList();
      setBooks(list);
    } catch {
      setBooks([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadBooks(); }, []);

  const handleScan = async () => {
    setScanning(true);
    setStatus("扫描中...");
    setScanLogs([]);
    try {
      const result = await api.scanAudiobooks();
      setScanLogs(result.logs || []);
      if (result.imported > 0) {
        setStatus(`扫描完成：导入 ${result.imported} 本`);
      } else if (result.covers_fetched > 0) {
        setStatus(`扫描完成：更新 ${result.covers_fetched} 个封面`);
      } else if (result.skipped > 0) {
        setStatus("扫描完成：没有新的有声书");
      } else {
        setStatus("扫描完成：未发现有声书");
      }
      await loadBooks();
    } catch {
      setStatus("扫描失败");
    } finally {
      setScanning(false);
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setImporting(true);
    setStatus("导入中...");
    try {
      await api.importAudiobookZip(file);
      setStatus(`导入成功: ${file.name}`);
      await loadBooks();
    } catch {
      setStatus("导入失败");
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (deleteFiles: boolean) => {
    if (!deleteModal) return;
    try {
      await api.deleteAudiobook(deleteModal.id, deleteFiles);
      if (deleteFiles) {
        setStatus(`已删除《${deleteModal.name}》及原始文件`);
      } else {
        setStatus(`已从书架移除《${deleteModal.name}》`);
      }
      setDeleteModal(null);
      await loadBooks();
    } catch {
      setStatus("删除失败");
    }
  };

  const handleBookClick = (book: AudiobookItem) => {
    navigate(
      `/audiobook/play?book_key=${encodeURIComponent(book.book_key)}&book_name=${encodeURIComponent(book.name)}`
    );
  };

  const handleSetCover = async () => {
    if (!coverModal || !coverModal.url.trim()) return;
    setSettingCover(true);
    try {
      await api.setAudiobookCover(coverModal.book.id, coverModal.url.trim());
      setStatus(`《${coverModal.book.name}》封面已更新`);
      setCoverModal(null);
      await loadBooks();
    } catch {
      setStatus("封面设置失败，请检查链接是否正确");
    } finally {
      setSettingCover(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[20px] font-bold text-[#1d1d1f]">有声书</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={handleScan}
            disabled={scanning}
            className="px-3 py-1.5 rounded-lg text-[13px] font-medium bg-black/[0.05] text-[#1d1d1f] hover:bg-black/[0.08] active:bg-black/[0.10] disabled:opacity-50 transition-colors"
          >
            {scanning ? "扫描中..." : "扫描"}
          </button>
          <button
            onClick={handleImportClick}
            disabled={importing}
            className="px-3 py-1.5 rounded-lg text-[13px] font-medium bg-[#c45d35] text-white hover:bg-[#b05230] active:bg-[#a04828] disabled:opacity-50 transition-colors"
          >
            {importing ? "导入中..." : "+ ZIP"}
          </button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".zip"
        className="hidden"
        onChange={handleImportFile}
      />

      {status && (
        <p className="text-[12px] text-[#86868b] mb-2">{status}</p>
      )}

      {scanLogs.length > 0 && (
        <div className="mb-4 p-3 rounded-lg bg-black/[0.02] border border-black/[0.04] max-h-48 overflow-y-auto">
          {scanLogs.map((log, i) => (
            <p key={i} className="text-[11px] text-[#86868b] leading-relaxed">
              {log}
            </p>
          ))}
        </div>
      )}

      {loading ? (
        <p className="text-[13px] text-[#c7c7cc] py-12 text-center">加载中</p>
      ) : books.length === 0 ? (
        <div className="py-16 text-center">
          <p className="text-[14px] text-[#86868b] mb-2">暂无有声书</p>
          <p className="text-[12px] text-[#c7c7cc]">
            将有声书文件夹放入 data/audiobooks/ 后点击"扫描"，<br />
            或点击"+ ZIP"上传 ZIP 包
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {books.map((book) => (
            <div
              key={book.id}
              onClick={() => handleBookClick(book)}
              className="group cursor-pointer"
            >
              <div className="aspect-square rounded-xl bg-gradient-to-br from-[#c45d35]/10 to-[#c45d35]/5 flex items-center justify-center text-[48px] mb-2 relative overflow-hidden">
                <span>🎧</span>
                <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => { e.stopPropagation(); setCoverModal({ book, url: "" }); }}
                    className="w-6 h-6 rounded-full bg-blue-500/80 text-white text-[12px] flex items-center justify-center"
                    title="设置封面"
                  >
                    🖼
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setDeleteModal(book); }}
                    className="w-6 h-6 rounded-full bg-black/50 text-white text-[12px] flex items-center justify-center"
                  >
                    ×
                  </button>
                </div>
              </div>
              <h3 className="text-[13px] font-medium text-[#1d1d1f] truncate">{book.name}</h3>
              <p className="text-[11px] text-[#86868b]">{book.total_chapters} 章</p>
            </div>
          ))}
        </div>
      )}
      {coverModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setCoverModal(null)}>
          <div className="bg-white rounded-xl p-5 w-[90%] max-w-sm" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-[15px] font-medium text-[#1d1d1f] mb-1">设置封面</h3>
            <p className="text-[12px] text-[#86868b] mb-3">《{coverModal.book.name}》</p>
            <input
              type="url"
              placeholder="粘贴豆瓣链接，如 https://book.douban.com/subject/27598664"
              value={coverModal.url}
              onChange={(e) => setCoverModal({ ...coverModal, url: e.target.value })}
              className="w-full px-3 py-2 text-[13px] border border-black/10 rounded-lg mb-3 outline-none focus:border-[#c45d35]"
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setCoverModal(null)}
                className="px-3 py-1.5 text-[13px] text-[#86868b] hover:bg-black/5 rounded-lg"
              >
                取消
              </button>
              <button
                onClick={handleSetCover}
                disabled={settingCover || !coverModal.url.trim()}
                className="px-3 py-1.5 text-[13px] font-medium text-white bg-[#c45d35] rounded-lg hover:bg-[#b05230] disabled:opacity-50"
              >
                {settingCover ? "获取中..." : "确认"}
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setDeleteModal(null)}>
          <div className="bg-white rounded-xl p-5 w-[90%] max-w-sm" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-[15px] font-medium text-[#1d1d1f] mb-2">删除有声书</h3>
            <p className="text-[13px] text-[#86868b] mb-4">《{deleteModal.name}》</p>
            <div className="space-y-2 mb-4">
              <button
                onClick={() => handleDelete(false)}
                className="w-full px-3 py-2.5 text-[13px] text-left rounded-lg border border-black/10 hover:bg-black/5"
              >
                <span className="font-medium text-[#1d1d1f]">仅从书架移除</span>
                <span className="block text-[11px] text-[#86868b] mt-0.5">保留原始文件，可重新扫描添加</span>
              </button>
              <button
                onClick={() => handleDelete(true)}
                className="w-full px-3 py-2.5 text-[13px] text-left rounded-lg border border-red-200 hover:bg-red-50"
              >
                <span className="font-medium text-red-600">删除原始文件</span>
                <span className="block text-[11px] text-[#86868b] mt-0.5">同时删除磁盘上的音频文件，不可恢复</span>
              </button>
            </div>
            <button
              onClick={() => setDeleteModal(null)}
              className="w-full px-3 py-1.5 text-[13px] text-[#86868b] hover:bg-black/5 rounded-lg"
            >
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
