/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        studio: {
          950: '#07090f',
          900: '#0d111d',
          800: '#151b2e',
          700: '#1f2842',
        },
      },
    },
  },
  plugins: [],
}
