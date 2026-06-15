import { Outlet, NavLink } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
}

type InstallPromptMode = "deferred" | "manual" | "ios";

const tabs = [
  { to: "/", label: "首页", mobileLabel: "首页" },
  { to: "/audiobook", label: "有声书", mobileLabel: "有声书" },
  { to: "/shelf", label: "书架", mobileLabel: "书架" },
  { to: "/settings", label: "设置", mobileLabel: "设置" },
];

export default function Layout() {
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [installPromptMode, setInstallPromptMode] = useState<InstallPromptMode | null>(null);
  const [showInstallPrompt, setShowInstallPrompt] = useState(false);
  const [version, setVersion] = useState("");
  const shellContainerClass = "w-full max-w-[1440px] mx-auto px-4 md:px-8 lg:px-10 xl:px-12";

  const isStandalone = useMemo(() => {
    const mq = window.matchMedia?.("(display-mode: standalone)");
    const iosStandalone = (window.navigator as Navigator & { standalone?: boolean }).standalone;
    return Boolean(mq?.matches || iosStandalone);
  }, []);

  useEffect(() => {
    const onOnline = () => setIsOffline(false);
    const onOffline = () => setIsOffline(true);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    if (isStandalone) return;

    const dismissedAt = Number(localStorage.getItem("pwa_install_dismissed_at") || "0");
    const cooldownMs = 24 * 60 * 60 * 1000;
    if (dismissedAt && Date.now() - dismissedAt < cooldownMs) return;

    const ua = window.navigator.userAgent;
    const isAndroid = /android/i.test(ua);
    const isIos = /iphone|ipad|ipod/i.test(ua);

    if (isIos) {
      setInstallEvent(null);
      setInstallPromptMode("ios");
      setShowInstallPrompt(true);
      return;
    }

    if (!isAndroid) {
      return;
    }

    let hasDeferredPrompt = false;
    const handler = (event: Event) => {
      event.preventDefault();
      hasDeferredPrompt = true;
      setInstallEvent(event as BeforeInstallPromptEvent);
      setInstallPromptMode("deferred");
      setShowInstallPrompt(true);
    };

    const onInstalled = () => {
      setInstallEvent(null);
      setInstallPromptMode(null);
      setShowInstallPrompt(false);
    };

    window.addEventListener("beforeinstallprompt", handler);
    window.addEventListener("appinstalled", onInstalled);

    const fallbackTimer = window.setTimeout(() => {
      if (!hasDeferredPrompt) {
        setInstallEvent(null);
        setInstallPromptMode("manual");
        setShowInstallPrompt(true);
      }
    }, 1800);

    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
      window.removeEventListener("appinstalled", onInstalled);
      window.clearTimeout(fallbackTimer);
    };
  }, [isStandalone]);

  useEffect(() => {
    fetch("/api/version")
      .then((res) => res.json())
      .then((data) => setVersion(typeof data?.version === "string" ? data.version : ""))
      .catch(() => setVersion(""));
  }, []);

  const handleInstall = async () => {
    if (installEvent && installPromptMode === "deferred") {
      await installEvent.prompt();
      const result = await installEvent.userChoice;
      setInstallEvent(null);
      setInstallPromptMode(null);
      setShowInstallPrompt(false);
      if (result.outcome === "dismissed") {
        localStorage.setItem("pwa_install_dismissed_at", String(Date.now()));
      }
      return;
    }

    localStorage.setItem("pwa_install_dismissed_at", String(Date.now()));
    setInstallEvent(null);
    setInstallPromptMode(null);
    setShowInstallPrompt(false);
  };

  const dismissInstallPrompt = () => {
    localStorage.setItem("pwa_install_dismissed_at", String(Date.now()));
    setInstallEvent(null);
    setInstallPromptMode(null);
    setShowInstallPrompt(false);
  };

  const installPromptText =
    installPromptMode === "ios"
      ? "在 Safari 中点击“分享”，再选择“添加到主屏幕”，即可安装 EasyReader。"
      : installPromptMode === "manual"
      ? "可在浏览器菜单中选择“添加到主屏幕”，安装后可获得更稳定的离线阅读体验。"
      : "安装到手机主屏，获得更稳定的离线阅读体验。";

  const installActionLabel = installPromptMode === "deferred" ? "立即安装" : "我知道了";
  const installDismissLabel = installPromptMode === "deferred" ? "稍后" : "关闭";

  return (
    <div className="min-h-full bg-[#fafafa]">
      {isOffline && (
        <div className="z-50 bg-[#b42318] text-white border-b border-[#8f1c13]">
          <div className={`${shellContainerClass} py-2 text-[12px] font-medium`}>
            当前离线模式：可继续阅读已缓存章节，联网后会自动恢复同步。
          </div>
        </div>
      )}

      {showInstallPrompt && !isOffline && installPromptMode && (
        <div className="z-50 bg-[#0a66c2] text-white border-b border-[#09569f]">
          <div className={`${shellContainerClass} py-2 flex items-center gap-3`}>
            <p className="text-[12px] flex-1">{installPromptText}</p>
            <button
              onClick={handleInstall}
              className="px-2.5 py-1 rounded-md bg-white text-[#0a66c2] text-[12px] font-semibold"
            >
              {installActionLabel}
            </button>
            <button
              onClick={dismissInstallPrompt}
              className="px-2 py-1 rounded-md bg-white/15 text-white text-[12px]"
            >
              {installDismissLabel}
            </button>
          </div>
        </div>
      )}

      {/* Desktop header */}
      <header className="hidden md:block sticky top-0 z-40 bg-[#fafafa]/85 backdrop-blur-xl border-b border-black/[0.04]">
        <div className={`${shellContainerClass} h-14 flex items-center justify-between`}>
          <div className="flex items-end gap-2">
            <span className="text-[16px] font-bold tracking-tight text-[#1d1d1f]">EasyReader</span>
            {version && <span className="text-[11px] text-[#86868b] tabular-nums">{version}</span>}
          </div>
          <nav className="flex items-center gap-1">
            {tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                className={({ isActive }) =>
                  `px-4 py-1.5 rounded-lg text-[13px] font-medium transition-all duration-200 ${
                    isActive
                      ? "text-[#1d1d1f] bg-black/[0.05]"
                      : "text-[#86868b] hover:text-[#1d1d1f] hover:bg-black/[0.03]"
                  }`
                }
              >
                {tab.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="pb-[68px] md:pb-8">
        <div className={`${shellContainerClass} pt-4 md:pt-8`}>
          <Outlet />
        </div>
      </main>

      {/* Mobile tab bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-xl border-t border-black/[0.06]">
        <div className="flex items-stretch justify-around h-[52px]">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center justify-center gap-[2px] transition-colors ${
                  isActive ? "text-[#1d1d1f]" : "text-[#c7c7cc]"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`w-[5px] h-[5px] rounded-full transition-all duration-300 ${
                    isActive ? "bg-[#c45d35] scale-100" : "bg-transparent scale-0"
                  }`} />
                  <span className="text-[11px] font-medium">{tab.mobileLabel}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
