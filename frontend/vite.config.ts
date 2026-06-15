import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

const clientVersion = process.env.npm_package_version || "0.1.0";
const apiContractVersion = "2026-06-11";

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(clientVersion),
    __API_CONTRACT_VERSION__: JSON.stringify(apiContractVersion),
  },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "inline",
      filename: "reader-sw.js",
      manifest: {
        name: "EasyReader",
        short_name: "EasyReader",
        description: "Self-hosted book reader",
        theme_color: "#1a1a2e",
        background_color: "#1a1a2e",
        display: "standalone",
        orientation: "any",
        start_url: "/",
        icons: [
          {
            src: "/icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        skipWaiting: true,
        clientsClaim: true,
        runtimeCaching: [
          {
            // Books list — NetworkFirst with 24-hour cache fallback
            urlPattern: /\/api\/books$/,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-books",
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 1, maxAgeSeconds: 86400 },
            },
          },
          {
            // Offline catalog & tasks — NetworkFirst with 24-hour fallback
            urlPattern: /\/api\/offline\/(catalog|tasks)/,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-offline",
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 20, maxAgeSeconds: 86400 },
            },
          },
          {
            // Reading progress pull — NetworkFirst, short cache
            urlPattern: /\/api\/sync\/progress\/pull/,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-sync-progress",
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 10, maxAgeSeconds: 3600 },
            },
          },
          {
            // Book metadata & chapter list (TOC) — NetworkFirst with 24-hour fallback
            urlPattern: /\/api\/content\/(book-info|chapters)/,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-content-meta",
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 100, maxAgeSeconds: 86400 },
            },
          },
          {
            // Chapter content — NetworkFirst with long-lived fallback for offline reading
            urlPattern: /\/api\/content\/chapter/,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-content-chapter",
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 3000, maxAgeSeconds: 2592000 },
            },
          },
          {
            // Audiobook media files — CacheFirst with long expiration
            urlPattern: /\/api\/media\//,
            handler: "CacheFirst",
            options: {
              cacheName: "audiobook-media",
              expiration: {
                maxEntries: 200,
                maxAgeSeconds: 2592000,
              },
              rangeRequests: true,
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8080",
    },
  },
});
