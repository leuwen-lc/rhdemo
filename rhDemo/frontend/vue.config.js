/**
 * Configuration Vue CLI pour le projet RHDemo
 *
 * Fix pour mode headless Firefox : désactiver defer sur les scripts
 * pour assurer le chargement en environnement staging
 */
const { defineConfig } = require('@vue/cli-service');

module.exports = defineConfig({
  // Utiliser des chemins relatifs pour compatibilité local/staging
  publicPath: './',

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

  // Configuration des pages avec scriptLoading
  pages: {
    index: {
      entry: 'src/main.js',
      template: 'public/index.html',
      filename: 'index.html',
      title: 'Gestion des Employés',
      // IMPORTANT: Force le chargement synchrone des scripts (pas defer)
      // pour fix Firefox headless qui ne charge pas les scripts defer
      scriptLoading: 'blocking'
    }
  }
});
