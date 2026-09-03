/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        vajra: {
          bg: "#0b0f17",
          panel: "#111827",
          panel2: "#161d2b",
          border: "#232c3d",
          accent: "#7c5cff",
          accent2: "#22d3ee",
        },
      },
    },
  },
  plugins: [],
};
