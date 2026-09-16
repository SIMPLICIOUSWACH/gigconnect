/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        navy: {
          50: '#f0f4f9',
          100: '#dae3ee',
          500: '#2c4a6e',
          600: '#1f3a5a',
          700: '#16304c',
          900: '#0c1e33',
        },
      },
    },
  },
  plugins: [],
}
