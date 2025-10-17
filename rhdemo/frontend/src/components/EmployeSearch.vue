<template>
  <div class="employe-search">
    <h2>Rechercher un Employé par ID</h2>
    
    <div class="search-form">
      <div class="input-group">
        <label for="employeId">ID de l'employé :</label>
        <input 
          id="employeId"
          v-model="searchId" 
          type="number" 
          placeholder="Entrez l'ID de l'employé"
          @keyup.enter="searchEmploye"
        />
      </div>
      <button @click="searchEmploye" :disabled="!searchId || loading">
        {{ loading ? 'Recherche...' : 'Rechercher' }}
      </button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    
    <div v-if="employe" class="employe-result">
      <h3>Employé trouvé :</h3>
      <div class="employe-card">
        <p><strong>ID :</strong> {{ employe.id }}</p>
        <p><strong>Prénom :</strong> {{ employe.prenom }}</p>
        <p><strong>Nom :</strong> {{ employe.nom }}</p>
        <p><strong>Email :</strong> {{ employe.mail }}</p>
        <div class="actions">
          <router-link :to="`/front/employe/${employe.id}`" class="btn btn-primary">
            Voir les détails
          </router-link>
          <router-link :to="`/front/edition/${employe.id}`" class="btn btn-secondary">
            Modifier
          </router-link>
        </div>
      </div>
    </div>

    <div class="navigation">
      <router-link to="/front/" class="btn btn-back">← Retour au menu principal</router-link>
    </div>
  </div>
</template>

<script>
import { getEmploye } from '../services/api';

export default {
  name: 'EmployeSearch',
  data() {
    return {
      searchId: '',
      employe: null,
      loading: false,
      error: ''
    };
  },
  methods: {
    async searchEmploye() {
      if (!this.searchId) return;
      
      this.loading = true;
      this.error = '';
      this.employe = null;
      
      try {
        const response = await getEmploye(this.searchId);
        this.employe = response.data;
      } catch (err) {
        this.error = 'Employé non trouvé ou erreur de connexion';
      } finally {
        this.loading = false;
      }
    }
  }
};
</script>

<style scoped>
.employe-search {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

.search-form {
  display: flex;
  gap: 15px;
  align-items: end;
  margin-bottom: 20px;
}

.input-group {
  flex: 1;
}

.input-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.input-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
}

button {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

button:hover:not(:disabled) {
  background: #0056b3;
}

.error {
  color: #dc3545;
  background: #f8d7da;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

.employe-result {
  margin: 20px 0;
}

.employe-card {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
}

.employe-card p {
  margin: 10px 0;
}

.actions {
  margin-top: 15px;
  display: flex;
  gap: 10px;
}

.btn {
  padding: 8px 16px;
  text-decoration: none;
  border-radius: 4px;
  display: inline-block;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-back {
  background: #28a745;
  color: white;
}

.btn:hover {
  opacity: 0.9;
}

.navigation {
  margin-top: 30px;
}
</style>