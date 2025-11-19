/**
 * Configuration Vue CLI pour le projet RHDemo
 */
const { defineConfig } = require('@vue/cli-service');

module.exports = defineConfig({
  // Configuration pour le dev server local
  devServer: {
    port: 8081,
    // Proxy vers le backend Spring Boot pendant le développement
    proxy: {
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true
      }
    }
  },

  // Optimisations de build
  productionSourceMap: false,

  // Configuration des pages
  pages: {
    index: {
      entry: 'src/main.js',
      template: 'public/index.html',
      filename: 'index.html',
      title: 'Gestion des Employés'
      // scriptLoading par défaut: 'defer' pour meilleures performances
    }
  }
});
