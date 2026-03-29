/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brand Unsafe surface hierarchy
        "obs-base":    "#140728",
        "obs-bg":      "#1a0c2d",
        "obs-low":     "#221536",
        "obs-mid":     "#26193a",
        "obs-high":    "#312345",
        "obs-top":     "#3c2e51",
        "obs-bright":  "#413255",
        // Accent / semantic
        "vio":         "#c3c1ff",
        "vio-deep":    "#5b53ff",
        "vio-text":    "#eddcff",
        "muted":       "#c7c4d9",
        "teal":        "#47d6ff",
        "teal-dark":   "#007893",
        "rose":        "#ffb4ab",
        "rose-dark":   "#93000a",
        "outline-dim": "#464556",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
