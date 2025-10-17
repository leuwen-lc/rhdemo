<template>
  <div class="employe-modify">
    <h2>Modifier un Employé par ID</h2>

    <div class="search-form">
      <div class="input-group">
        <label for="modifyId">ID de l'employé à modifier :</label>
        <input 
          id="modifyId"
          v-model="modifyId" 
          type="number" 
          placeholder="Entrez l'ID de l'employé"
          @keyup.enter="searchEmployeToModify"
        />
      </div>
      <button @click="searchEmployeToModify" :disabled="!modifyId || loading">
        {{ loading ? 'Recherche...' : 'Rechercher' }}
      </button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    
    <div v-if="employe" class="employe-preview">
      <h3>Employé à modifier :</h3>
      <div class="employe-card">
        <p><strong>ID :</strong> {{ employe.id }}</p>
        <p><strong>Prénom :</strong> {{ employe.prenom }}</p>
        <p><strong>Nom :</strong> {{ employe.nom }}</p>
        <p><strong>Email :</strong> {{ employe.mail }}</p>
      </div>
      
      <div class="actions">
        <router-link :to="`/front/edition/${employe.id}`" class="btn btn-primary">
          ✏️ Modifier cet employé
        </router-link>
        <router-link :to="`/front/employe/${employe.id}`" class="btn btn-secondary">
          👁️ Voir les détails
        </router-link>
      </div>
    </div>

    <div class="navigation">
      <router-link to="/front/" class="btn btn-back">← Retour au menu principal</router-link>
      <router-link to="/front/employes" class="btn btn-list">Voir tous les employés</router-link>
    </div>
  </div>
</template>

<script>
import { getEmploye } from '../services/api';

export default {
  name: 'EmployeModify',
  data() {
    return {
      modifyId: '',
      employe: null,
      loading: false,
      error: ''
    };
  },
  methods: {
    async searchEmployeToModify() {
      if (!this.modifyId) return;
      
      this.loading = true;
      this.error = '';
      this.employe = null;
      
      try {
        const response = await getEmploye(this.modifyId);
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
.employe-modify {
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

.employe-preview {
  margin: 20px 0;
}

.employe-card {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.employe-card p {
  margin: 10px 0;
}

.actions {
  display: flex;
  gap: 15px;
  justify-content: center;
  margin: 20px 0;
}

.btn {
  padding: 12px 24px;
  text-decoration: none;
  border-radius: 4px;
  display: inline-block;
  font-weight: bold;
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

.btn-list {
  background: #17a2b8;
  color: white;
}

.btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.navigation {
  margin-top: 30px;
  display: flex;
  gap: 15px;
  justify-content: center;
}
</style>