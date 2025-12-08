// Script de debug et gestion d'erreurs pour Vue.js
console.log('[DEBUG] HTML chargé, JS fonctionne');
window.__VUE_DEBUG__ = true;
window.__VUE_ERRORS__ = [];

// Capturer les erreurs JavaScript
window.addEventListener('error', function(e) {
  console.error('[ERROR]', e.message, e.filename, e.lineno, e.colno);
  window.__VUE_ERRORS__.push({
    message: e.message,
    file: e.filename,
    line: e.lineno,
    col: e.colno
  });
});

// Capturer les erreurs non gérées des promises
window.addEventListener('unhandledrejection', function(e) {
  console.error('[PROMISE ERROR]', e.reason);
  window.__VUE_ERRORS__.push({
    message: 'Promise rejection: ' + e.reason
  });
});
