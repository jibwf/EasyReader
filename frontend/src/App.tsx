import { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "./components/common/Layout";
import Home from "./pages/Home";
import Search from "./pages/Search";
import BookDetail from "./pages/BookDetail";
import Read from "./pages/Read";
import Shelf from "./pages/Shelf";
import Manga from "./pages/Manga";
import Audiobook from "./pages/Audiobook";
import AudiobookPlayer from "./pages/AudiobookPlayer";
import OfflineCatalog from "./pages/OfflineCatalog";
import Settings from "./pages/Settings";
import { LoginDialog } from "./components/LoginDialog";
import { api } from "@/api/client";
import { getClientIdentity } from "@/utils/client-identity";
import { flushSyncProgressQueue } from "@/utils/sync-queue";

function useVersionCheck() {
  useEffect(() => {
    api.getVersion()
      .then((data) => {
        const stored = localStorage.getItem("app_version");
        if (stored && stored !== data.version) {
          localStorage.setItem("app_version", data.version);
          window.location.reload();
        } else {
          localStorage.setItem("app_version", data.version);
        }
      })
      .catch(() => {});
  }, []);
}

function useAuthCheck() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("reader-auth-token");
    const expires = localStorage.getItem("reader-auth-expires");

    if (!token || !expires || Date.now() > Number(expires)) {
      setAuthenticated(false);
      return;
    }

    fetch(`/api/auth/verify?token=${token}`)
      .then(res => res.json())
      .then(data => setAuthenticated(data.valid))
      .catch(() => setAuthenticated(false));
  }, []);

  return { authenticated, setAuthenticated };
}

export default function App() {
  useVersionCheck();
  const { authenticated, setAuthenticated } = useAuthCheck();

  useEffect(() => {
    const flush = () => {
      const identity = getClientIdentity();
      flushSyncProgressQueue(async (payload) => {
        const result = await api.upsertSyncProgress(payload);
        if (!result.accepted && result.conflict) {
          throw new Error("sync conflict");
        }
        return result;
      }).then(() => {
        return api.pullSyncProgress(identity.userId, 0, 1);
      }).catch(() => {});
    };

    flush();
    window.addEventListener("online", flush);
    return () => window.removeEventListener("online", flush);
  }, []);

  if (authenticated === null) {
    return <div className="flex items-center justify-center h-screen">加载中...</div>;
  }

  if (!authenticated) {
    return <LoginDialog onLogin={() => setAuthenticated(true)} />;
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/manga" element={<Manga />} />
        <Route path="/audiobook" element={<Audiobook />} />
        <Route path="/shelf" element={<Shelf />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/offline-catalog" element={<OfflineCatalog />} />
        <Route path="/search" element={<Search />} />
        <Route path="/book" element={<BookDetail />} />
      </Route>
      <Route path="/read" element={<Read />} />
      <Route path="/audiobook/play" element={<AudiobookPlayer />} />
    </Routes>
  );
}
