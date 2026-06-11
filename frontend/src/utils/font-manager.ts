export interface FontOption {
  key: string;
  name: string;
  family: string;
  description: string;
  source: string;
  license: string;
}

export const FONT_OPTIONS: FontOption[] = [
  {
    key: "noto-sans-cjk-sc",
    name: "思源黑体（Noto Sans CJK SC）",
    family: '"Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
    description: "无衬线，结构稳定，墨水屏正文和列表都清晰。",
    source: "notofonts / Noto CJK",
    license: "SIL OFL 1.1",
  },
  {
    key: "noto-serif-cjk-sc",
    name: "思源宋体（Noto Serif CJK SC）",
    family: '"Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "STSong", serif',
    description: "衬线字重心稳，长章节阅读更耐看。",
    source: "notofonts / Noto CJK",
    license: "SIL OFL 1.1",
  },
  {
    key: "lxgw-wenkai",
    name: "霞鹜文楷（LXGW WenKai）",
    family: '"LXGW WenKai", "Kaiti SC", "STKaiti", serif',
    description: "中文显示友好，纸感强，适合休闲阅读。",
    source: "GitHub / lxgw",
    license: "SIL OFL 1.1",
  },
  {
    key: "cangle-song-w05",
    name: "仓耳与墨 W05",
    family: '"仓耳与墨W05", "Microsoft YaHei", sans-serif',
    description: "几何风格笔画，对比度高，墨水屏显示清晰。",
    source: "Cangle Software",
    license: "Cangle SIL License",
  },
];

const FONT_STORAGE_KEY = "reader_font_key";

const DEFAULT_FONT_KEY = "noto-sans-cjk-sc";

function resolveFontByKey(fontKey: string, fallbackKey: string): FontOption {
  return (
    FONT_OPTIONS.find((item) => item.key === fontKey)
    || FONT_OPTIONS.find((item) => item.key === fallbackKey)
    || FONT_OPTIONS[0]
  );
}

function isValidFontKey(fontKey: string | null): fontKey is string {
  return Boolean(fontKey && FONT_OPTIONS.some((item) => item.key === fontKey));
}

function readStoredFontKey(): string {
  const raw = window.localStorage.getItem(FONT_STORAGE_KEY);
  if (isValidFontKey(raw)) {
    return raw;
  }

  return DEFAULT_FONT_KEY;
}

export interface FontPreferences {
  fontKey: string;
}

export function getFontPreferences(): FontPreferences {
  return {
    fontKey: readStoredFontKey(),
  };
}

export function applyFontPreferences(preferences = getFontPreferences()): FontPreferences {
  const selectedFont = resolveFontByKey(preferences.fontKey, DEFAULT_FONT_KEY);
  const root = document.documentElement;
  root.style.setProperty("--app-font-family", selectedFont.family);
  root.style.setProperty("--reader-font-family", selectedFont.family);
  window.localStorage.setItem(FONT_STORAGE_KEY, selectedFont.key);
  return { fontKey: selectedFont.key };
}

export function setFontPreference(fontKey: string): FontPreferences {
  const next = resolveFontByKey(fontKey, DEFAULT_FONT_KEY);
  window.localStorage.setItem(FONT_STORAGE_KEY, next.key);
  return applyFontPreferences({ fontKey: next.key });
}
