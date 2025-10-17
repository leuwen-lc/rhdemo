<template>
  <div class="employe-delete">
    <h2>Supprimer un Employé par ID</h2>
    
    <div class="warning-box">
      ⚠️ <strong>Attention :</strong> Cette action est irréversible !
    </div>

    <div class="search-form">
      <div class="input-group">
        <label for="deleteId">ID de l'employé à supprimer :</label>
        <input 
          id="deleteId"
          v-model="deleteId" 
          type="number" 
          placeholder="Entrez l'ID de l'employé"
          @keyup.enter="searchEmployeToDelete"
        />
      </div>
      <button @click="searchEmployeToDelete" :disabled="!deleteId || loading">
        {{ loading ? 'Recherche...' : 'Rechercher' }}
      </button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="success" class="success">{{ success }}</div>
    
    <div v-if="employe && !deleted" class="employe-preview">
      <h3>Employé à supprimer :</h3>
      <div class="employe-card">
        <p><strong>ID :</strong> {{ employe.id }}</p>
        <p><strong>Prénom :</strong> {{ employe.prenom }}</p>
        <p><strong>Nom :</strong> {{ employe.nom }}</p>
        <p><strong>Email :</strong> {{ employe.mail }}</p>
      </div>
      
      <div class="confirmation">
        <p><strong>Êtes-vous sûr de vouloir supprimer cet employé ?</strong></p>
        <div class="actions">
          <button @click="confirmDelete" :disabled="deleting" class="btn btn-danger">
            {{ deleting ? 'Suppression...' : 'Oui, supprimer' }}
          </button>
          <button @click="cancelDelete" class="btn btn-secondary">
            Annuler
          </button>
        </div>
      </div>
    </div>

    <div class="navigation">
      <router-link to="/front/" class="btn btn-back">← Retour au menu principal</router-link>
      <router-link to="/front/employes" class="btn btn-list">Voir tous les employés</router-link>
    </div>
  </div>
</template>

<script>
import { getEmploye, deleteEmploye } from '../services/api';

export default {
  name: 'EmployeDelete',
  data() {
    return {
      deleteId: '',
      employe: null,
      loading: false,
      deleting: false,
      deleted: false,
      error: '',
      success: ''
    };
  },
  methods: {
    async searchEmployeToDelete() {
      if (!this.deleteId) return;
      
      this.loading = true;
      this.error = '';
      this.success = '';
      this.employe = null;
      this.deleted = false;
      
      try {
        const response = await getEmploye(this.deleteId);
        this.employe = response.data;
      } catch (err) {
        this.error = 'Employé non trouvé ou erreur de connexion';
      } finally {
        this.loading = false;
      }
    },
    
    async confirmDelete() {
      this.deleting = true;
      this.error = '';
      
      try {
        await deleteEmploye(this.employe.id);
        this.success = `Employé ${this.employe.prenom} ${this.employe.nom} supprimé avec succès`;
        this.deleted = true;
        this.employe = null;
        this.deleteId = '';
      } catch (err) {
        this.error = 'Erreur lors de la suppression de l\'employé';
      } finally {
        this.deleting = false;
      }
    },
    
    cancelDelete() {
      this.employe = null;
      this.deleteId = '';
      this.error = '';
    }
  }
};
</script>

<style scoped>
.employe-delete {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

.warning-box {
  background: #fff3cd;
  border: 1px solid #ffeaa7;
  color: #856404;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 20px;
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
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

button:disabled {
  background: #6c757d;
  color: white;
  cursor: not-allowed;
}

.error {
  color: #dc3545;
  background: #f8d7da;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

.success {
  color: #155724;
  background: #d4edda;
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

.confirmation {
  background: #ffe6e6;
  border: 1px solid #ffcccc;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.actions {
  margin-top: 15px;
  display: flex;
  gap: 10px;
  justify-content: center;
}

.btn {
  padding: 10px 20px;
  text-decoration: none;
  border-radius: 4px;
  display: inline-block;
  border: none;
  cursor: pointer;
}

.btn-danger {
  background: #dc3545;
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
  background: #007bff;
  color: white;
}

.btn:hover:not(:disabled) {
  opacity: 0.9;
}

.navigation {
  margin-top: 30px;
  display: flex;
  gap: 15px;
}
</style>