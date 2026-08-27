import type { Config } from "tailwindcss";

// Design tokens mirror apps/web/src/app/globals.css (blueprint §D.4): gold-on-ink.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        gold: {
          50: "#FDF8E8",
          100: "#FBF0C4",
          200: "#F6E190",
          300: "#EFCD5B",
          400: "#E5B93C",
          500: "#D4AF37",
          600: "#B38F1F",
          700: "#8E6F17",
          800: "#6A5310",
          900: "#48370A",
        },
        ink: {
          50: "#E8E8EA",
          100: "#C4C4C8",
          200: "#97979E",
          300: "#6A6A74",
          400: "#4A4A54",
          500: "#2D2D36",
          600: "#1E1E26",
          700: "#161620",
          800: "#10101A",
          900: "#08080F",
        },
        success: "#3FB950",
        warning: "#D29922",
        danger: "#F85149",
        info: "#58A6FF",
        // Violet — the `provisional` state hue: distinct from certified (green), failed (red),
        // stale (amber), never_certified (blue) and in_training (gold). "Held, not final."
        accent: "#A371F7",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["'Playfair Display'", "serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
