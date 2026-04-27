import { defineConfig } from 'vite';
import { devtools } from '@tanstack/devtools-vite';
import { tanstackStart } from '@tanstack/react-start/plugin/vite';
import viteReact from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { nitro } from 'nitro/vite';

const config = defineConfig({
  build: {
    outDir: 'dist',
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    watch: {
      usePolling: true,
    },
  },
  resolve: {
    tsconfigPaths: true,
  },
  plugins: [
    devtools(),
    nitro({
      // decimal.js-light has "main": "decimal" (no extension) in package.json
      // which breaks ESM resolution when externalized. Force inline bundling.
      externals: { inline: ['decimal.js-light'] },
    }),
    tailwindcss(),
    tanstackStart(),
    viteReact(),
  ],
});

export default config;
