<template>
  <div class="home-menu">
    <h2>Menu Principal - Gestion des Employés</h2>
    <div class="menu-grid">
      <div class="menu-item">
        <h3>Consultation</h3>
        <router-link to="/front/employes" class="menu-link">
          📋 Voir tous les employés
        </router-link>
        <router-link to="/front/recherche" class="menu-link">
          🔍 Rechercher un employé par ID
        </router-link>
      </div>
      
      <div class="menu-item">
        <h3>Gestion</h3>
        <router-link to="/front/ajout" class="menu-link">
          ➕ Ajouter un nouvel employé
        </router-link>
        <router-link to="/front/suppression" class="menu-link">
          🗑️ Supprimer un employé par ID
        </router-link>
      </div>
      
      <div class="menu-item">
        <h3>Modification</h3>
        <router-link to="/front/modification" class="menu-link">
          ✏️ Modifier un employé par ID
        </router-link>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'HomeMenu'
};
</script>

<style scoped>
.home-menu {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.menu-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-top: 30px;
}

.menu-item {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
}

.menu-item h3 {
  margin-top: 0;
  color: #495057;
  border-bottom: 2px solid #007bff;
  padding-bottom: 10px;
}

.menu-link {
  display: block;
  padding: 12px 16px;
  margin: 10px 0;
  background: #007bff;
  color: white;
  text-decoration: none;
  border-radius: 5px;
  transition: background-color 0.3s;
}

.menu-link:hover {
  background: #0056b3;
}
</style>