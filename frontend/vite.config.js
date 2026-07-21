import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        port: 5173,
        proxy: {
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
    // `npm run preview -- --host` serves the production build for the phone demo
    // (more stable than dev/HMR). Binds all interfaces so the iPhone can reach it
    // over the Tailscale IP, allows any host header, and proxies /api to the
    // local backend so the SPA still talks to Jarvis on :8000.
    preview: {
        port: 4173,
        host: true,
        allowedHosts: true,
        proxy: {
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
});
