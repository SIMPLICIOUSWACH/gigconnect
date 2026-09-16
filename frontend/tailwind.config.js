/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: {
          DEFAULT: '#1F3864',
          hover: '#16294A',
          light: '#E9EEF5',
        },
        ink: '#1A1F2B',
        muted: '#5F6B7A',
        bg: '#F7F8FA',
        surface: '#FFFFFF',
        border: '#E2E5EA',
        accent: {
          DEFAULT: '#2F6B4F',
          light: '#E8F1EC',
        },
      },
      fontSize: {
        'page-title': ['28px', { lineHeight: '36px', fontWeight: '600' }],
        'section-title': ['18px', { lineHeight: '26px', fontWeight: '600' }],
        body: ['16px', { lineHeight: '24px', fontWeight: '400' }],
        label: ['14px', { lineHeight: '20px', fontWeight: '500' }],
        caption: ['13px', { lineHeight: '18px', fontWeight: '400' }],
        nav: ['15px', { lineHeight: '20px', fontWeight: '500' }],
      },
    },
  },
  plugins: [],
}
