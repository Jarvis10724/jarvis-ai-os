/** @type {import('tailwindcss').Config} */

// Reads each color from a CSS custom property (set per-theme in index.css)
// so the same `bg-jarvis-*` / `text-jarvis-*` classes used throughout the
// app automatically repaint for light vs. dark mode — no per-component
// changes needed. Still supports Tailwind's opacity modifiers (e.g.
// `bg-jarvis-panel2/50`) via the `<alpha-value>` placeholder.
function themeColor(varName) {
  return `rgb(var(${varName}) / <alpha-value>)`;
}

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        jarvis: {
          bg: themeColor("--jarvis-bg"),
          panel: themeColor("--jarvis-panel"),
          panel2: themeColor("--jarvis-panel2"),
          panel3: themeColor("--jarvis-panel3"),
          border: themeColor("--jarvis-border"),
          "border-soft": themeColor("--jarvis-border-soft"),
          cyan: themeColor("--jarvis-cyan"),
          cyan2: themeColor("--jarvis-cyan2"),
          "cyan-dim": themeColor("--jarvis-cyan-dim"),
          blue: themeColor("--jarvis-blue"),
          violet: themeColor("--jarvis-violet"),
          amber: themeColor("--jarvis-amber"),
          rose: themeColor("--jarvis-rose"),
          emerald: themeColor("--jarvis-emerald"),
          text: themeColor("--jarvis-text"),
          muted: themeColor("--jarvis-muted"),
          faint: themeColor("--jarvis-faint"),
        },
      },
      fontFamily: {
        display: ["Space Grotesk", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        glow: "0 0 28px rgba(45, 212, 240, 0.22)",
        "glow-sm": "0 0 14px rgba(45, 212, 240, 0.20)",
        "glow-lg": "0 0 56px rgba(45, 212, 240, 0.20)",
        "inner-glow": "inset 0 0 30px rgba(45, 212, 240, 0.06)",
        elevated: "0 12px 32px -12px rgba(0, 0, 0, 0.55)",
        "elevated-lg": "0 24px 64px -20px rgba(0, 0, 0, 0.65)",
        "glass-edge": "inset 0 1px 0 0 rgba(255, 255, 255, 0.05)",
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(45,212,240,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(45,212,240,0.05) 1px, transparent 1px)",
        "radial-glow": "radial-gradient(circle at 50% 0%, rgba(45,212,240,0.13), transparent 60%)",
        aurora:
          "radial-gradient(ellipse 80% 50% at 20% -10%, rgba(45,212,240,0.18), transparent 60%), radial-gradient(ellipse 60% 40% at 90% 10%, rgba(139,92,246,0.12), transparent 55%)",
        "glass-sheen": "linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0) 40%)",
      },
      backgroundSize: {
        grid: "40px 40px",
      },
      transitionTimingFunction: {
        premium: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-4px)" },
        },
        // Slow ambient drift for the global aurora backdrop — big enough to
        // read as "alive," slow enough to never distract from content.
        auroraDrift: {
          "0%, 100%": { backgroundPosition: "0% 0%, 100% 0%" },
          "50%": { backgroundPosition: "8% 6%, 92% 10%" },
        },
        // Continuous slow rotation for JarvisCore's outer ring/conic glow.
        spinSlow: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        spinSlowReverse: {
          "0%": { transform: "rotate(360deg)" },
          "100%": { transform: "rotate(0deg)" },
        },
        // JarvisCore idle "breathing" — gentle scale + glow swell.
        orbBreathe: {
          "0%, 100%": { transform: "scale(1)", filter: "brightness(1)" },
          "50%": { transform: "scale(1.05)", filter: "brightness(1.15)" },
        },
        // Expanding rings while listening — like a voice waveform pushing outward.
        ringExpand: {
          "0%": { transform: "scale(0.8)", opacity: "0.7" },
          "100%": { transform: "scale(1.8)", opacity: "0" },
        },
        // Equalizer bars while Jarvis is speaking.
        eqBounce: {
          "0%, 100%": { transform: "scaleY(0.3)" },
          "50%": { transform: "scaleY(1)" },
        },
        // Diagonal holographic sheen sweeping across a hovered panel.
        holoSweep: {
          "0%": { transform: "translateX(-120%) translateY(-120%) rotate(20deg)" },
          "100%": { transform: "translateX(120%) translateY(120%) rotate(20deg)" },
        },
        // "Energy flowing toward a node" — animates the dash offset on the
        // orbital shell's core-to-node connection lines.
        dashFlow: {
          "0%": { strokeDashoffset: "24" },
          "100%": { strokeDashoffset: "0" },
        },
        // Slow-drifting starfield dots behind the orbital shell.
        starDrift: {
          "0%, 100%": { transform: "translate(0, 0)" },
          "50%": { transform: "translate(-12px, 8px)" },
        },
        // The AI Core's ambient bloom — a soft energy swell while idle.
        coreBloom: {
          "0%, 100%": { opacity: "0.45", transform: "translate(-50%, -50%) scale(1)" },
          "50%": { opacity: "0.8", transform: "translate(-50%, -50%) scale(1.08)" },
        },
        // Faster, brighter bloom while Jarvis is processing.
        coreBloomActive: {
          "0%, 100%": { opacity: "0.7", transform: "translate(-50%, -50%) scale(1.04)" },
          "50%": { opacity: "1", transform: "translate(-50%, -50%) scale(1.16)" },
        },
        // A single energy pulse ring expanding out from the core.
        corePulseRing: {
          "0%": { transform: "translate(-50%, -50%) scale(0.55)", opacity: "0.55" },
          "100%": { transform: "translate(-50%, -50%) scale(1.5)", opacity: "0" },
        },
        // Gentle per-particle twinkle so the field doesn't read as static.
        particleTwinkle: {
          "0%, 100%": { opacity: "0.25" },
          "50%": { opacity: "0.9" },
        },
      },
      animation: {
        pulseGlow: "pulseGlow 2.5s ease-in-out infinite",
        scan: "scan 3s linear infinite",
        fadeInUp: "fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both",
        shimmer: "shimmer 2s linear infinite", // powers the .skeleton class in index.css
        float: "float 4s ease-in-out infinite",
        auroraDrift: "auroraDrift 18s ease-in-out infinite",
        spinSlow: "spinSlow 12s linear infinite",
        spinSlowReverse: "spinSlowReverse 16s linear infinite",
        orbBreathe: "orbBreathe 3.2s ease-in-out infinite",
        ringExpand: "ringExpand 1.8s cubic-bezier(0.16, 1, 0.3, 1) infinite",
        eqBounce: "eqBounce 0.9s ease-in-out infinite",
        holoSweep: "holoSweep 1.1s cubic-bezier(0.16, 1, 0.3, 1)",
        dashFlow: "dashFlow 1.4s linear infinite",
        starDrift: "starDrift 24s ease-in-out infinite",
        coreBloom: "coreBloom 5s ease-in-out infinite",
        coreBloomActive: "coreBloomActive 1.6s ease-in-out infinite",
        corePulseRing: "corePulseRing 3.4s cubic-bezier(0.16, 1, 0.3, 1) infinite",
        particleTwinkle: "particleTwinkle 3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
