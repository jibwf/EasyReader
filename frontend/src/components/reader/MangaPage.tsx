import { useState, useCallback } from "react";

interface Props {
  images: string[];
  sourceUrl: string;
}

export default function MangaPage({ images, sourceUrl }: Props) {
  const [currentPage, setCurrentPage] = useState(0);

  const proxyUrl = (url: string) =>
    `/api/proxy/image?url=${encodeURIComponent(url)}&referer=${encodeURIComponent(sourceUrl)}`;

  const goNext = useCallback(() => {
    if (currentPage < images.length - 1) setCurrentPage((p) => p + 1);
  }, [currentPage, images.length]);

  const goPrev = useCallback(() => {
    if (currentPage > 0) setCurrentPage((p) => p - 1);
  }, [currentPage]);

  const handleClick = (e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (x < rect.width / 3) {
      goPrev();
    } else {
      goNext();
    }
  };

  if (images.length === 0) return null;

  return (
    <div className="w-full h-[calc(100vh-52px)] flex flex-col items-center justify-center bg-black relative">
      {/* Image */}
      <div
        className="flex-1 w-full flex items-center justify-center overflow-hidden cursor-pointer"
        onClick={handleClick}
      >
        <img
          src={proxyUrl(images[currentPage])}
          alt={`page ${currentPage + 1}`}
          className="max-w-full max-h-full object-contain"
        />
      </div>

      {/* Page indicator */}
      <div className="absolute bottom-16 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-black/60 text-white text-[11px] tabular-nums">
        {currentPage + 1} / {images.length}
      </div>

      {/* Preload adjacent pages */}
      {currentPage + 1 < images.length && (
        <link rel="preload" as="image" href={proxyUrl(images[currentPage + 1])} />
      )}
    </div>
  );
}
