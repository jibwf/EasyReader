import { useRef, useState } from "react";

interface Props {
  images: string[];
  sourceUrl: string;
}

export default function MangaScroll({ images, sourceUrl }: Props) {
  const [loadedSet, setLoadedSet] = useState<Set<number>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);

  const proxyUrl = (url: string) =>
    `/api/proxy/image?url=${encodeURIComponent(url)}&referer=${encodeURIComponent(sourceUrl)}`;

  return (
    <div ref={containerRef} className="w-full max-w-reader mx-auto">
      {images.map((url, i) => (
        <div key={i} className="w-full relative">
          {!loadedSet.has(i) && (
            <div className="w-full aspect-[3/4] bg-black/[0.03] flex items-center justify-center">
              <span className="text-[12px] text-[#c7c7cc]">{i + 1} / {images.length}</span>
            </div>
          )}
          <img
            src={proxyUrl(url)}
            alt={`page ${i + 1}`}
            loading="lazy"
            className={`w-full h-auto block ${loadedSet.has(i) ? "" : "absolute top-0 left-0"}`}
            onLoad={() => setLoadedSet((s) => new Set(s).add(i))}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        </div>
      ))}
    </div>
  );
}
