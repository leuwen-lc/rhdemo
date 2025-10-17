<template>
  <div class="employe-form">
    <h2>{{ isEditing ? "✏️ Modification" : "➕ Ajout" }} d'un Employé</h2>
    
    <div v-if="loading" class="loading">Chargement des données...</div>
    
    <form @submit.prevent="submit" class="form" v-if="!loading">
      <div class="form-group">
        <label for="prenom">Prénom *</label>
        <input 
          id="prenom"
          v-model="localEmploye.prenom" 
          type="text"
          placeholder="Prénom de l'employé" 
          required 
        />
      </div>
      
      <div class="form-group">
        <label for="nom">Nom *</label>
        <input 
          id="nom"
          v-model="localEmploye.nom" 
          type="text"
          placeholder="Nom de l'employé" 
          required 
        />
      </div>
      
      <div class="form-group">
        <label for="mail">Email *</label>
        <input 
          id="mail"
          v-model="localEmploye.mail" 
          type="email"
          placeholder="email@exemple.com" 
          required 
        />
      </div>
      
      <div class="form-group">
        <label for="motdepasse">{{ isEditing ? "Nouveau mot de passe" : "Mot de passe" }} *</label>
        <input 
          id="motdepasse"
          v-model="localEmploye.motdepasse" 
          type="password"
          placeholder="Mot de passe" 
          required 
        />
      </div>
      
      <div class="form-actions">
        <button type="submit" :disabled="saving" class="btn btn-primary">
          {{ saving ? 'Sauvegarde...' : (isEditing ? 'Modifier' : 'Ajouter') }}
        </button>
        <button type="button" @click="cancel" class="btn btn-secondary">
          Annuler
        </button>
      </div>
    </form>
    
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="success" class="success">{{ success }}</div>
  </div>
</template>
<script>
import { getEmploye, saveEmploye } from '../services/api';

export default {
  name: 'EmployeForm',
  data() {
    return {
      localEmploye: {
        prenom: "",
        nom: "",
        mail: "",
        motdepasse: "",
        id: null
      },
      loading: false,
      saving: false,
      error: "",
      success: ""
    };
  },
  computed: {
    isEditing() {
      return !!this.$route.params.id;
    }
  },
  async created() {
    if (this.isEditing) {
      await this.loadEmploye();
    }
  },
  methods: {
    async loadEmploye() {
      this.loading = true;
      this.error = "";
      
      try {
        const res = await getEmploye(this.$route.params.id);
        this.localEmploye = { ...res.data };
        // Vider le mot de passe pour la sécurité
        this.localEmploye.motdepasse = "";
      } catch (e) {
        this.error = "Erreur lors du chargement de l'employé";
        console.error('Erreur de chargement:', e);
      } finally {
        this.loading = false;
      }
    },
    
    async submit() {
      this.saving = true;
      this.error = "";
      this.success = "";
      
      try {
        const employeToSave = { ...this.localEmploye };
        // Pour la modification, si le mot de passe est vide, ne pas l'envoyer
        if (this.isEditing && !employeToSave.motdepasse) {
          delete employeToSave.motdepasse;
        }
        
        const result = await saveEmploye(employeToSave);
        this.success = `Employé ${this.isEditing ? 'modifié' : 'ajouté'} avec succès !`;
        
        // Rediriger après un délai pour montrer le message de succès
        setTimeout(() => {
          this.$router.push('/front/employes');
        }, 1500);
        
      } catch (e) {
        this.error = `Erreur lors de la ${this.isEditing ? 'modification' : 'création'} de l'employé`;
        console.error('Erreur de sauvegarde:', e.response?.data || e.message);
      } finally {
        this.saving = false;
      }
    },
    
    cancel() {
      this.$router.push('/front/employes');
    }
  }
};
</script>

<style scoped>
.employe-form {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

.loading {
  text-align: center;
  font-size: 18px;
  color: #007bff;
  margin: 40px 0;
}

.form {
  background: white;
  padding: 30px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
  color: #333;
}

.form-group input {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #e1e5e9;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 0.3s;
}

.form-group input:focus {
  outline: none;
  border-color: #007bff;
}

.form-actions {
  display: flex;
  gap: 15px;
  justify-content: center;
  margin-top: 30px;
}

.btn {
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  min-width: 120px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background: #545b62;
}

.error {
  color: #dc3545;
  background: #f8d7da;
  border: 1px solid #f5c6cb;
  padding: 15px;
  border-radius: 8px;
  margin: 20px 0;
  text-align: center;
}

.success {
  color: #155724;
  background: #d4edda;
  border: 1px solid #c3e6cb;
  padding: 15px;
  border-radius: 8px;
  margin: 20px 0;
  text-align: center;
}

/* Responsive design */
@media (max-width: 768px) {
  .form {
    padding: 20px;
  }
  
  .form-actions {
    flex-direction: column;
  }
  
  .btn {
    width: 100%;
  }
}
</style>