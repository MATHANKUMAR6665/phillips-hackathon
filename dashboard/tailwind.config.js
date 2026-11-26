/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        finance: {
          dark: '#0F172A',
          card: '#1E293B',
          border: '#334155',
          accent: '#3B82F6',
          positive: '#10B981',
          negative: '#EF4444',
          warning: '#F59E0B'
        }
      }
    },
  },
  plugins: [],
}