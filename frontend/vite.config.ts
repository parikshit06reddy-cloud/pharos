import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API routes to the Pharos backend on :8000 during dev.
const API = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "^/(api|brief|health|model-card|data-passport|audit-log|session)": {
        target: API,
        changeOrigin: true,
      },
    },
  },
});
