/**
 * Configuration Vue CLI pour le projet RHDemo
 *
 * Fix pour mode headless Firefox : désactiver defer sur les scripts
 * pour assurer le chargement en environnement staging
 */
module.exports = {
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

  // IMPORTANT: Désactiver 'defer' sur les scripts pour fix headless Firefox
  chainWebpack: config => {
    // Désactiver les attributs defer sur les scripts
    // En mode headless, Firefox peut avoir des problèmes avec defer
    config.plugin('html').tap(args => {
      args[0].scriptLoading = 'blocking'; // Au lieu de 'defer'
      return args;
    });
  },

  // Configuration des pages (single page app)
  pages: {
    index: {
      entry: 'src/main.js',
      template: 'public/index.html',
      filename: 'index.html',
      title: 'Gestion des Employés'
    }
  }
};
