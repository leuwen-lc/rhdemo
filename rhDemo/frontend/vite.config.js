/**
 * Configuration Vite pour le projet RHDemo
 */
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],

  // Dev server local
  server: {
    port: 8081,
    // Proxy vers le backend Spring Boot pendant le développement
    proxy: {
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true
      }
    }
  },

  build: {
    outDir: 'dist',
    sourcemap: false,
    // Bundle unique : Element Plus est enregistré globalement (main.js)
    chunkSizeWarningLimit: 1500
  }
});
