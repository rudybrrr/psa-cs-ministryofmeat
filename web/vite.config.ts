/// <reference types="vitest/config" />
import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    fs: {
      allow: [repoRoot],
    },
    proxy: {
      "/synthetic": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/incidents": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/agent-runs": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/carrier-recovery-cases": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/allocation-tradeoff-reviews": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/cargo-safety-reviews": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
  },
});
