/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Press Start 2P"', 'monospace'],
        data: ['"VT323"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
};
