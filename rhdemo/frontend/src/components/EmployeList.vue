<template>
  <div class="employe-list">
    <h2>📋 Liste de tous les Employés</h2>
    
    <div class="actions-bar">
      <button @click="$router.push('/front/ajout')" class="btn btn-primary">
        ➕ Ajouter un employé
      </button>
      <button @click="fetchEmployes" class="btn btn-secondary">
        🔄 Actualiser
      </button>
    </div>
    
    <div v-if="loading" class="loading">Chargement...</div>
    <div v-if="error" class="error">{{ error }}</div>
    
    <div v-if="employes.length > 0" class="employes-grid">
      <div v-for="employe in employes" :key="employe.id" class="employe-card">
        <div class="employe-info">
          <h3>{{ employe.prenom }} {{ employe.nom }}</h3>
          <p>📧 {{ employe.mail }}</p>
          <p>🆔 ID: {{ employe.id }}</p>
        </div>
        <div class="employe-actions">
          <router-link :to="`/front/employe/${employe.id}`" class="btn btn-info">
            👁️ Voir
          </router-link>
          <button @click="edit(employe.id)" class="btn btn-warning">
            ✏️ Editer
          </button>
          <button @click="del(employe.id)" class="btn btn-danger">
            🗑️ Supprimer
          </button>
        </div>
      </div>
    </div>
    
    <div v-else-if="!loading && !error" class="no-data">
      <p>Aucun employé trouvé.</p>
      <button @click="$router.push('/front/ajout')" class="btn btn-primary">
        ➕ Ajouter le premier employé
      </button>
    </div>
  </div>
</template>
<script>
import { getEmployes, deleteEmploye } from '../services/api';
export default {
  data() {
    return {
      employes: [],
      loading: false,
      error: ''
    };
  },
  methods: {
    async fetchEmployes() {
      this.loading = true;
      this.error = '';
      try {
        const res = await getEmployes();
        this.employes = res.data;
      } catch (e) {
        this.error = 'Erreur de chargement';
      } finally {
        this.loading = false;
      }
    },
    async del(id) {
      try {
        await deleteEmploye(id);
        this.fetchEmployes();
      } catch (e) {
        this.error = 'Erreur lors de la suppression';
      }
    },
    edit(id) {
      this.$router.push(`/front/edition/${id}`);
    }
  },
  created() {
    this.fetchEmployes();
  }
};
</script>

<style scoped>
.employe-list {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.actions-bar {
  display: flex;
  gap: 15px;
  margin-bottom: 30px;
  justify-content: center;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  font-weight: bold;
  text-decoration: none;
  display: inline-block;
  transition: all 0.3s;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-info {
  background: #17a2b8;
  color: white;
}

.btn-warning {
  background: #ffc107;
  color: #212529;
}

.btn-danger {
  background: #dc3545;
  color: white;
}

.btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}

.loading {
  text-align: center;
  font-size: 18px;
  color: #007bff;
  margin: 40px 0;
}

.error {
  color: #dc3545;
  background: #f8d7da;
  padding: 15px;
  border-radius: 5px;
  margin: 20px 0;
  text-align: center;
}

.employes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.employe-card {
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  transition: transform 0.3s, box-shadow 0.3s;
}

.employe-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 16px rgba(0,0,0,0.15);
}

.employe-info h3 {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 1.2em;
}

.employe-info p {
  margin: 5px 0;
  color: #666;
  font-size: 0.9em;
}

.employe-actions {
  display: flex;
  gap: 8px;
  margin-top: 15px;
  justify-content: space-between;
}

.employe-actions .btn {
  flex: 1;
  padding: 8px 12px;
  font-size: 12px;
  text-align: center;
}

.no-data {
  text-align: center;
  margin: 60px 0;
  color: #666;
}

.no-data p {
  font-size: 18px;
  margin-bottom: 20px;
}

/* Responsive design */
@media (max-width: 768px) {
  .employes-grid {
    grid-template-columns: 1fr;
  }
  
  .actions-bar {
    flex-direction: column;
    align-items: center;
  }
  
  .employe-actions {
    flex-direction: column;
  }
  
  .employe-actions .btn {
    margin: 2px 0;
  }
}
</style>