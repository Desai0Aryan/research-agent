import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#eef2ff", 100: "#e0e7ff", 400: "#818cf8", 500: "#6366f1", 600: "#4f46e5", 700: "#4338ca" },
      },
      boxShadow: { glow: "0 0 0 1px rgba(99,102,241,.25), 0 8px 30px -8px rgba(99,102,241,.45)" },
      keyframes: {
        fadeUp: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: { fadeUp: "fadeUp .35s ease both", shimmer: "shimmer 1.6s infinite" },
    },
  },
  plugins: [],
} satisfies Config;
