/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'Geist Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        shell: {
          950: 'rgb(var(--ff-shell-950) / <alpha-value>)',
          900: 'rgb(var(--ff-shell-900) / <alpha-value>)',
          800: 'rgb(var(--ff-shell-800) / <alpha-value>)',
          700: 'rgb(var(--ff-shell-700) / <alpha-value>)',
        },
        brand: {
          violet: 'rgb(var(--ff-brand-violet) / <alpha-value>)',
          amber: 'rgb(var(--ff-brand-amber) / <alpha-value>)',
          cyan: 'rgb(var(--ff-brand-cyan) / <alpha-value>)',
        },
        ink: {
          50: 'rgb(var(--ff-ink-50) / <alpha-value>)',
          200: 'rgb(var(--ff-ink-200) / <alpha-value>)',
          300: 'rgb(var(--ff-ink-300) / <alpha-value>)',
          400: 'rgb(var(--ff-ink-400) / <alpha-value>)',
          500: 'rgb(var(--ff-ink-500) / <alpha-value>)',
          700: 'rgb(var(--ff-ink-700) / <alpha-value>)',
        },
      },
      boxShadow: {
        soft: '0 18px 60px -24px rgb(0 0 0 / 0.55)',
        panel: '0 18px 60px -28px rgb(0 0 0 / 0.68)',
        glow: '0 0 0 1px rgb(var(--ff-brand-violet) / 0.18), 0 20px 60px -24px rgb(0 0 0 / 0.7)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'panel-in': {
          '0%': { opacity: '0', transform: 'translateY(6px) scale(0.99)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'soft-pulse': {
          '0%, 100%': { opacity: '0.55' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        'fade-up': 'fade-up 180ms ease-out',
        'panel-in': 'panel-in 160ms ease-out',
        'soft-pulse': 'soft-pulse 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
