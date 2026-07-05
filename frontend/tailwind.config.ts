import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAFAF8",
        surface: "#FFFFFF",
        ink: {
          DEFAULT: "#15171A",
          muted: "#5B5F66",
          faint: "#8A8D92",
        },
        line: "#E3E3DF",
        safe: {
          DEFAULT: "#16794F",
          bg: "#EAF6EF",
        },
        caution: {
          DEFAULT: "#B45309",
          bg: "#FDF3E7",
        },
        risky: {
          DEFAULT: "#C2410C",
          bg: "#FDEEE6",
        },
        danger: {
          DEFAULT: "#B91C1C",
          bg: "#FDECEC",
        },
        primary: {
          DEFAULT: "#1D4ED8",
          hover: "#1739A8",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        "fade-in": "fade-in 0.35s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
