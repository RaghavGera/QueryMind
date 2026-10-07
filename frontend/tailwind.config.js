/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        base: {
          950: "#07070b",
          900: "#0b0b12",
          850: "#0f0f18",
          800: "#14141f",
          700: "#1c1c2b",
          600: "#26263a",
          500: "#33334a",
        },
        line: {
          DEFAULT: "rgba(255,255,255,0.08)",
          soft: "rgba(255,255,255,0.05)",
          strong: "rgba(255,255,255,0.14)",
        },
        ink: {
          DEFAULT: "#f4f4f7",
          dim: "#a3a3b3",
          faint: "#6b6b80",
        },
        accent: {
          violet: "#8b7bff",
          indigo: "#6366f1",
          cyan: "#5eead4",
          glow: "#a78bfa",
          // "Needs attention" only (ambiguity, clarification).
          amber: "#fbbf24",
          // Results / answers.
          magenta: "#f472b6",
        },
        state: {
          success: "#4ade80",
          warning: "#facc15",
          danger: "#fb7185",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      backgroundImage: {
        "grid-fade":
          "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.06) 1px, transparent 0)",
        "radial-glow":
          "radial-gradient(60% 60% at 50% 0%, rgba(139,123,255,0.16) 0%, rgba(7,7,11,0) 70%)",
      },
      backgroundSize: {
        grid: "28px 28px",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(139,123,255,0.25), 0 0 40px rgba(139,123,255,0.15)",
        "glow-sm": "0 0 0 1px rgba(139,123,255,0.2), 0 0 16px rgba(139,123,255,0.12)",
        card: "0 1px 0 rgba(255,255,255,0.04) inset, 0 20px 40px -20px rgba(0,0,0,0.6)",
      },
      keyframes: {
        pulseGlow: {
          "0%,100%": { opacity: 0.6 },
          "50%": { opacity: 1 },
        },
        fadeUp: {
          from: { opacity: 0, transform: "translateY(8px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        caret: {
          "0%,49%": { opacity: 1 },
          "50%,100%": { opacity: 0 },
        },
        glitch: {
          "0%,100%": { transform: "translate(0)", clipPath: "inset(0 0 0 0)" },
          "20%": { transform: "translate(-2px, 1px)", clipPath: "inset(10% 0 55% 0)" },
          "40%": { transform: "translate(2px, -1px)", clipPath: "inset(60% 0 8% 0)" },
          "60%": { transform: "translate(-1px, 0)", clipPath: "inset(30% 0 35% 0)" },
          "80%": { transform: "translate(1px, 1px)", clipPath: "inset(75% 0 2% 0)" },
        },
        aurora: {
          "0%,100%": { transform: "translate3d(0,0,0) scale(1)" },
          "50%": { transform: "translate3d(4%,-3%,0) scale(1.08)" },
        },
        beam: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
        grain: {
          "0%,100%": { transform: "translate(0,0)" },
          "25%": { transform: "translate(-3%,2%)" },
          "50%": { transform: "translate(2%,-3%)" },
          "75%": { transform: "translate(-2%,-1%)" },
        },
        scrollCue: {
          "0%": { transform: "scaleY(0)", transformOrigin: "top" },
          "45%": { transform: "scaleY(1)", transformOrigin: "top" },
          "55%": { transform: "scaleY(1)", transformOrigin: "bottom" },
          "100%": { transform: "scaleY(0)", transformOrigin: "bottom" },
        },
      },
      animation: {
        "pulse-glow": "pulseGlow 2.4s ease-in-out infinite",
        "fade-up": "fadeUp 0.5s ease both",
        shimmer: "shimmer 2.5s linear infinite",
        caret: "caret 1s steps(1) infinite",
        glitch: "glitch 0.45s steps(2) infinite",
        aurora: "aurora 18s ease-in-out infinite",
        beam: "beam 1.6s cubic-bezier(0.4,0,0.2,1) infinite",
        grain: "grain 1.2s steps(4) infinite",
        "scroll-cue": "scrollCue 2.2s cubic-bezier(0.65,0,0.35,1) infinite",
      },
    },
  },
  plugins: [],
};
