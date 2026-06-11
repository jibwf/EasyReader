import {
  normalizeReaderTheme,
  useReaderStore,
  type AutoPageTurnSpeed,
  type NormalizedReaderTheme,
} from "@/stores/readerStore";

interface Props {
  onClose: () => void;
  autoPageTurnEnabled: boolean;
  onToggleAutoPageTurn: () => void;
}

const speedOptions: Array<{ key: AutoPageTurnSpeed; label: string; hint: string }> = [
  { key: "slow", label: "慢", hint: "12秒/页" },
  { key: "medium", label: "中", hint: "8秒/页" },
  { key: "fast", label: "快", hint: "5秒/页" },
];

const themeOptions: Array<{
  key: NormalizedReaderTheme;
  label: string;
  color: string;
  borderColor: string;
}> = [
  { key: "light", label: "默认", color: "#ffffff", borderColor: "#d1d1d6" },
  { key: "sepia", label: "米黄", color: "#f8f3eb", borderColor: "#d8ccb6" },
  { key: "mint", label: "护眼绿", color: "#edf6ee", borderColor: "#c8decb" },
  { key: "blue", label: "晴空蓝", color: "#edf3fb", borderColor: "#cad8ec" },
  { key: "gray", label: "雾灰", color: "#f0f2f5", borderColor: "#d0d3db" },
  { key: "night", label: "夜间", color: "#121316", borderColor: "#3a3d46" },
];

export default function ReaderSettings({ onClose, autoPageTurnEnabled, onToggleAutoPageTurn }: Props) {
  const { settings, updateSettings } = useReaderStore();
  const activeTheme = normalizeReaderTheme(settings.theme);
  const isNight = activeTheme === "night";

  const panelClass = isNight ? "bg-[#1b1c1f] text-[#e5e5e7]" : "bg-white text-[#1d1d1f]";
  const mutedTextClass = isNight ? "text-[#a7a7ad]" : "text-[#6e6e73]";
  const controlBorderClass = isNight ? "border-white/[0.16]" : "border-black/[0.12]";
  const panelBorderClass = isNight ? "border-white/[0.12]" : "border-black/[0.08]";
  const activeOptionClass = "border-[#c45d35] text-[#c45d35]";
  const inactiveOptionClass = isNight
    ? "border-white/[0.16] text-[#a7a7ad]"
    : "border-black/[0.12] text-[#6e6e73]";
  const controlBgClass = isNight ? "bg-white/[0.05] active:bg-white/[0.08]" : "bg-black/[0.03] active:bg-black/[0.06]";
  const dividerClass = isNight ? "border-white/[0.12]" : "border-black/[0.08]";

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 px-3 pb-3 md:items-center md:p-4"
      style={{ paddingBottom: "max(env(safe-area-inset-bottom), 0.75rem)" }}
      onClick={onClose}
    >
      <div
        className={`w-full max-w-lg max-h-[86vh] overflow-y-auto rounded-2xl p-5 shadow-xl border ${panelClass} ${panelBorderClass}`}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold mb-4">阅读设置</h3>

        {/* Font size */}
        <div className="flex items-center justify-between mb-4">
          <span className={`text-sm ${mutedTextClass}`}>字号</span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => updateSettings({ fontSize: Math.max(14, settings.fontSize - 2) })}
              className={`w-8 h-8 rounded border text-sm ${controlBorderClass} ${controlBgClass}`}
            >
              A-
            </button>
            <span className="text-sm w-8 text-center">{settings.fontSize}</span>
            <button
              onClick={() => updateSettings({ fontSize: Math.min(28, settings.fontSize + 2) })}
              className={`w-8 h-8 rounded border text-sm ${controlBorderClass} ${controlBgClass}`}
            >
              A+
            </button>
          </div>
        </div>

        {/* Line height */}
        <div className="flex items-center justify-between mb-4">
          <span className={`text-sm ${mutedTextClass}`}>行距</span>
          <div className="flex gap-2">
            {[1.5, 1.8, 2.0, 2.5].map((lh) => (
              <button
                key={lh}
                onClick={() => updateSettings({ lineHeight: lh })}
                className={`px-2 py-1 text-xs rounded border transition-colors ${
                  settings.lineHeight === lh
                    ? activeOptionClass
                    : inactiveOptionClass
                }`}
              >
                {lh}
              </button>
            ))}
          </div>
        </div>

        {/* Theme */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm ${mutedTextClass}`}>阅读背景</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {themeOptions.map((option) => (
              <button
                key={option.key}
                onClick={() => updateSettings({ theme: option.key })}
                className={`flex items-center gap-2 rounded-lg border px-2 py-2 text-xs transition-colors ${
                  activeTheme === option.key ? activeOptionClass : inactiveOptionClass
                }`}
              >
                <span
                  className="h-4 w-4 rounded-full border"
                  style={{ backgroundColor: option.color, borderColor: option.borderColor }}
                />
                <span>{option.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Padding */}
        <div className="flex items-center justify-between">
          <span className={`text-sm ${mutedTextClass}`}>边距</span>
          <div className="flex gap-2">
            {(["sm", "md", "lg"] as const).map((p) => (
              <button
                key={p}
                onClick={() => updateSettings({ padding: p })}
                className={`px-3 py-1 text-xs rounded border transition-colors ${
                  settings.padding === p
                    ? activeOptionClass
                    : inactiveOptionClass
                }`}
              >
                {{ sm: "小", md: "中", lg: "大" }[p]}
              </button>
            ))}
          </div>
        </div>

        {/* Auto page turn */}
        <div className={`mt-4 border-t pt-4 ${dividerClass}`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm ${mutedTextClass}`}>自动翻页</span>
            <button
              onClick={onToggleAutoPageTurn}
              className={`px-3 py-1 text-xs rounded border transition-colors ${
                autoPageTurnEnabled ? activeOptionClass : inactiveOptionClass
              }`}
            >
              {autoPageTurnEnabled ? "暂停" : "开始"}
            </button>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {speedOptions.map((option) => (
              <button
                key={option.key}
                onClick={() => updateSettings({ autoPageTurnSpeed: option.key })}
                className={`rounded-lg border px-2 py-2 text-xs transition-colors ${
                  settings.autoPageTurnSpeed === option.key ? activeOptionClass : inactiveOptionClass
                }`}
              >
                <div>{option.label}速</div>
                <div className={`mt-1 text-[10px] ${mutedTextClass}`}>{option.hint}</div>
              </button>
            ))}
          </div>
          <p className={`mt-2 text-[11px] ${mutedTextClass}`}>
            章节切换、手动滚动、打开目录或设置时会自动暂停。
          </p>
        </div>
      </div>
    </div>
  );
}
