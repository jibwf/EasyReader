import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api, type AudiobookItem } from "@/api/client";

export default function Audiobook() {
  const [books, setBooks] = useState<AudiobookItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [status, setStatus] = useState("");
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
    try {
      const result = await api.scanAudiobooks();
      if (result.imported > 0) {
        setStatus(`导入 ${result.imported} 本有声书`);
      } else if (result.skipped > 0) {
        setStatus("没有新的有声书");
      } else {
        setStatus("未发现有声书文件夹");
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

  const handleDelete = async (book: AudiobookItem, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`确定删除《${book.name}》？`)) return;
    try {
      await api.deleteAudiobook(book.id);
      setStatus(`已删除《${book.name}》`);
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
        <p className="text-[12px] text-[#86868b] mb-4">{status}</p>
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
                <button
                  onClick={(e) => handleDelete(book, e)}
                  className="absolute top-2 right-2 w-6 h-6 rounded-full bg-black/50 text-white text-[12px] opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
                >
                  ×
                </button>
              </div>
              <h3 className="text-[13px] font-medium text-[#1d1d1f] truncate">{book.name}</h3>
              <p className="text-[11px] text-[#86868b]">{book.total_chapters} 章</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
