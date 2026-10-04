/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Tokens de design exposés en variables CSS (src/index.css).
        // Tout le thème passe par là : clair et sombre cohabitent sans
        // overrides conditionnels dans les composants.
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar))',
          foreground: 'hsl(var(--sidebar-foreground))',
          border: 'hsl(var(--sidebar-border))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        success: 'hsl(var(--success))',
        warning: 'hsl(var(--warning))',
        danger: 'hsl(var(--danger))',
        accent: {
          blue: 'hsl(var(--accent-blue))',
          green: 'hsl(var(--accent-green))',
          purple: 'hsl(var(--accent-purple))',
          orange: 'hsl(var(--accent-orange))',
        },
        // Surfaces translucides des panneaux flottants (sidebar/navbar).
        surface: {
          DEFAULT: 'hsl(var(--surface))',
          border: 'hsl(var(--surface-border))',
          hover: 'hsl(var(--surface-hover))',
        },
        // Liserés verticaux des cartes KPI (un par indicateur).
        kpi: {
          blue: 'hsl(var(--kpi-blue))',
          green: 'hsl(var(--kpi-green))',
          purple: 'hsl(var(--kpi-purple))',
          orange: 'hsl(var(--kpi-orange))',
        },
        // Teinte du focus ring global (accessibilité clavier).
        ring: 'hsl(var(--ring))',
      },
      borderRadius: {
        card: '0.75rem',
        xl2: '1.25rem',
        xl3: '1.5rem',
      },
      boxShadow: {
        // Ombre douce et diffuse des panneaux flottants.
        float:
          '0 8px 32px -8px rgb(0 0 0 / 0.18), 0 2px 8px -2px rgb(0 0 0 / 0.08)',
      },
    },
  },
  plugins: [],
}
