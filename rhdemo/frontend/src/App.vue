<template>
  <div id="app">
    <header class="app-header">
      <h1>🏢 Système de Gestion des Employés</h1>
      <nav class="main-nav" v-if="$route.name !== 'home'">
        <router-link to="/front/" class="nav-link home-link">🏠 Accueil</router-link>
        <router-link to="/front/employes" class="nav-link">📋 Liste</router-link>
        <router-link to="/front/ajout" class="nav-link">➕ Ajouter</router-link>
        <router-link to="/front/recherche" class="nav-link">🔍 Rechercher</router-link>
      </nav>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script>
export default {
  name: 'App'
};
</script>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background-color: #f5f5f5;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: linear-gradient(135deg, #007bff, #0056b3);
  color: white;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.app-header h1 {
  margin: 0 0 15px 0;
  text-align: center;
  font-size: 2rem;
}

.main-nav {
  display: flex;
  justify-content: center;
  gap: 20px;
  flex-wrap: wrap;
}

.nav-link {
  color: white;
  text-decoration: none;
  padding: 8px 16px;
  border-radius: 20px;
  background: rgba(255,255,255,0.2);
  transition: all 0.3s;
  font-weight: 500;
}

.nav-link:hover {
  background: rgba(255,255,255,0.3);
  transform: translateY(-1px);
}

.nav-link.router-link-active {
  background: rgba(255,255,255,0.4);
  font-weight: bold;
}

.home-link {
  background: rgba(40,167,69,0.8) !important;
}

.home-link:hover {
  background: rgba(40,167,69,1) !important;
}

.app-main {
  flex: 1;
  padding: 20px;
}

/* Responsive design */
@media (max-width: 768px) {
  .app-header h1 {
    font-size: 1.5rem;
  }
  
  .main-nav {
    gap: 10px;
  }
  
  .nav-link {
    padding: 6px 12px;
    font-size: 0.9rem;
  }
  
  .app-main {
    padding: 15px;
  }
}
</style>