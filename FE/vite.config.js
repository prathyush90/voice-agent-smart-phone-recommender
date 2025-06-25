import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import wasm from 'vite-plugin-wasm';
import topLevelAwait from 'vite-plugin-top-level-await';

export default defineConfig({
  plugins: [
    react(),
    wasm(),
    topLevelAwait(),
  ],
  server: {
    allowedHosts: ['.ngrok-free.app'],
    port: 5173
  },
  assetsInclude: ['**/*.wasm'], // ensures Vite knows to treat .wasm files correctly
});
