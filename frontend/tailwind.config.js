/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Light theme. Token semantics preserved: ink = subtle fills + accent-button text;
        // surface/panel = card surfaces; mist = primary text; muted = secondary; line = borders.
        ink: "#eef2f8",
        surface: "#ffffff",
        panel: "#ffffff",
        line: "#dbe2ec",
        muted: "#5a6b85",
        mist: "#0f1b2e",
        beam: "#0d9488",
        grounded: "#047857",
        sev: {
          critical: "#dc2626",
          serious: "#ea580c",
          caution: "#b45309",
          info: "#2563eb",
        },
      },
      fontFamily: {
        display: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15,27,46,0.04), 0 10px 30px -16px rgba(15,27,46,0.18)",
      },
    },
  },
  plugins: [],
};
