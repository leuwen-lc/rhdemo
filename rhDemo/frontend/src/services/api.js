import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

// ==================== Protection CSRF ====================
// Intercepteur pour ajouter automatiquement le token CSRF depuis le cookie
// Spring Security 6+ utilise XOR encoding, mais le SpaCsrfTokenRequestHandler
// côté serveur gère le décodage automatiquement
api.interceptors.request.use(config => {
  // Récupérer le token CSRF depuis le cookie XSRF-TOKEN
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('XSRF-TOKEN='))
    ?.split('=')[1];
  
  // DEBUG: Afficher les informations CSRF
  /*if (['post', 'put', 'delete', 'patch'].includes(config.method)) {
    console.log('🔐 [CSRF] Requête:', config.method.toUpperCase(), config.url);
    console.log('🔐 [CSRF] Token trouvé:', csrfToken ? 'OUI (' + csrfToken.substring(0, 20) + '...)' : 'NON');
    console.log('🔐 [CSRF] Tous les cookies:', document.cookie);
  }*/
  
  // Ajouter le header X-XSRF-TOKEN pour les requêtes mutantes (POST, PUT, DELETE, PATCH)
  if (csrfToken && ['post', 'put', 'delete', 'patch'].includes(config.method)) {
    config.headers['X-XSRF-TOKEN'] = csrfToken;
  }
  
  return config;
}, error => {
  return Promise.reject(error);
});

// Intercepteur de réponse pour gérer les erreurs CSRF
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response && error.response.status === 403) {
      console.error('❌ [CSRF] Erreur 403 - Token CSRF invalide ou expiré');
      console.error('❌ [CSRF] Requête:', error.config.method.toUpperCase(), error.config.url);
      console.error('❌ [CSRF] Header envoyé:', error.config.headers['X-XSRF-TOKEN']?.substring(0, 20) + '...');
    }
    return Promise.reject(error);
  }
);
// =========================================================

export function getEmployes() {
  return api.get('/employes');
}

export function getEmployesPage(page = 0, size = 20, sort = null, order = 'ASC', filters = {}) {
  const params = { page, size };
  if (sort) {
    params.sort = sort;
    params.order = order;
  }
  if (filters.prenom) params.filterPrenom = filters.prenom;
  if (filters.nom) params.filterNom = filters.nom;
  if (filters.mail) params.filterMail = filters.mail;
  if (filters.adresse) params.filterAdresse = filters.adresse;
  return api.get('/employes/page', { params });
}

export function getEmploye(id) {
  return api.get(`/employes/${id}`);
}

export function createEmploye(employe) {
  const { id, ...data } = employe;
  return api.post('/employes', data);
}

export function updateEmploye(id, employe) {
  const { id: _, ...data } = employe;
  return api.put(`/employes/${id}`, data);
}

export function deleteEmploye(id) {
  return api.delete(`/employes/${id}`);
}

export function getUserInfo() {
  return api.get('/userinfo');
}