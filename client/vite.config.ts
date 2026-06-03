import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },

  server: {
    port: 1420,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },

  // Tauri expects a fixed port and a static dist directory
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },

  envPrefix: ["VITE_", "TAURI_"],
});
