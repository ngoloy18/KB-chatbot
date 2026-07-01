/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        med: {
          bg: "#F7FAFA",
          surface: "#FFFFFF",
          border: "#DDE7E6",
          primary: "#0F766E",
          deep: "#115E59",
          info: "#2D9CDB",
          success: "#16A34A",
          warning: "#D97706",
          error: "#DC2626",
          text: "#172A2A",
          muted: "#5F6F6D",
        },
      },
      boxShadow: {
        soft: "0 18px 44px rgba(23, 42, 42, 0.09)",
        glass: "0 20px 54px rgba(17, 94, 89, 0.14)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
