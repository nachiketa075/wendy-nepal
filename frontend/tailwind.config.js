/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        forest: '#163d2d',
        citrus: '#e5ed88',
        cream: '#faf9f0',
        sage: '#eef0e3',
        line: '#d9dfd2',
        amber: '#ca8a22',
        berry: '#9b2c2c',
      },
      fontFamily: {
        display: ['"Playfair Display"', 'Georgia', 'serif'],
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
