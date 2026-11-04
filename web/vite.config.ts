import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `npm run dev` proxies to a running `kiripix serve` (its default port).
const server = "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", emptyOutDir: true },
  server: { proxy: { "/api": server, "/files": server } },
});
