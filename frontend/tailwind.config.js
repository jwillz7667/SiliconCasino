/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        felt: {
          DEFAULT: "#1a5f2a",
          dark: "#0d3d18",
          light: "#2a7f3a",
        },
        casino: {
          gold: "#ffd700",
          red: "#dc2626",
          black: "#1a1a1a",
        },
      },
    },
  },
  plugins: [],
};
