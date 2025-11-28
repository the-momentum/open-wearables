import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      colors: {
        background: {
          DEFAULT: 'hsl(var(--background))',
          elevated: 'hsl(var(--background-elevated))',
        },
        foreground: {
          DEFAULT: 'hsl(var(--foreground))',
          muted: 'hsl(var(--foreground-muted))',
          subtle: 'hsl(var(--foreground-subtle))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          elevated: 'hsl(var(--card-elevated))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          hover: 'hsl(var(--primary-hover))',
          muted: 'hsl(var(--primary-muted))',
          glow: 'hsl(var(--primary-glow))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          hover: 'hsl(var(--secondary-hover))',
          muted: 'hsl(var(--secondary-muted))',
          glow: 'hsl(var(--secondary-glow))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          hover: 'hsl(var(--accent-hover))',
          muted: 'hsl(var(--accent-muted))',
          glow: 'hsl(var(--accent-glow))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          muted: 'hsl(var(--success-muted))',
          glow: 'hsl(var(--success-glow))',
          foreground: 'hsl(var(--success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          muted: 'hsl(var(--warning-muted))',
          glow: 'hsl(var(--warning-glow))',
          foreground: 'hsl(var(--warning-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          muted: 'hsl(var(--destructive-muted))',
          glow: 'hsl(var(--destructive-glow))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        border: {
          DEFAULT: 'hsl(var(--border))',
          hover: 'hsl(var(--border-hover))',
          glow: 'hsl(var(--border-glow))',
        },
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
        chart: {
          '1': 'hsl(var(--chart-1))',
          '2': 'hsl(var(--chart-2))',
          '3': 'hsl(var(--chart-3))',
          '4': 'hsl(var(--chart-4))',
          '5': 'hsl(var(--chart-5))',
        },
      },
      boxShadow: {
        'glow-primary': '0 0 20px hsla(185, 100%, 50%, 0.4), 0 0 40px hsla(185, 100%, 50%, 0.2)',
        'glow-secondary': '0 0 20px hsla(315, 100%, 60%, 0.4), 0 0 40px hsla(315, 100%, 60%, 0.2)',
        'glow-accent': '0 0 20px hsla(270, 100%, 65%, 0.4), 0 0 40px hsla(270, 100%, 65%, 0.2)',
        'glow-ambient': '0 0 30px hsla(185, 100%, 50%, 0.08)',
        'neon-sm': '0 0 10px hsla(185, 100%, 50%, 0.3)',
        'neon-md': '0 0 20px hsla(185, 100%, 50%, 0.4)',
        'neon-lg': '0 0 30px hsla(185, 100%, 50%, 0.5)',
      },
      transitionTimingFunction: {
        'out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      transitionDuration: {
        'fast': '150ms',
        'normal': '200ms',
        'slow': '300ms',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'float': 'float 3s ease-in-out infinite',
        'gradient': 'gradient 3s ease infinite',
        'shimmer': 'shimmer 2s ease-in-out infinite',
        'border-glow': 'border-glow-pulse 2s ease-in-out infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '0.7' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'gradient': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'border-glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 10px hsla(185, 100%, 50%, 0.2)' },
          '50%': { boxShadow: '0 0 20px hsla(185, 100%, 50%, 0.4)' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
