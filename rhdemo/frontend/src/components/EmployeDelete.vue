<template>
  <div>
    <el-row justify="center">
      <el-col :xs="24" :sm="18" :md="12" :lg="10">
        <el-card>
          <template #header>
            <h2 style="text-align: center; margin: 0;">🗑️ Supprimer un Employé par ID</h2>
          </template>
          
          <el-alert
            title="Attention : Cette action est irréversible !"
            type="warning"
            show-icon
            :closable="false"
            style="margin-bottom: 20px;"
          />

          <!-- Étape 1: Recherche de l'employé -->
          <el-card v-if="!employe || deleted" class="search-card">
            <template #header>
              <h3 style="margin: 0;">🔍 Rechercher l'employé à supprimer</h3>
            </template>
            
            <el-form @submit.prevent="searchEmployeToDelete">
              <el-form-item label="ID de l'employé à supprimer">
                <el-input
                  v-model="deleteId"
                  type="number"
                  placeholder="Entrez l'ID de l'employé"
                  @keyup.enter="searchEmployeToDelete"
                >
                  <template #append>
                    <el-button 
                      type="primary" 
                      :loading="loading"
                      :disabled="!deleteId"
                      @click="searchEmployeToDelete"
                    >
                      {{ loading ? 'Recherche...' : 'Rechercher' }}
                    </el-button>
                  </template>
                </el-input>
              </el-form-item>
            </el-form>
          </el-card>

          <el-alert
            v-if="error"
            :title="error"
            type="error"
            show-icon
            style="margin: 20px 0;"
          />
          
          <el-alert
            v-if="success"
            :title="success"
            type="success"
            show-icon
            style="margin: 20px 0;"
          />
          
          <!-- Étape 2: Confirmation de suppression -->
          <el-card v-if="employe && !deleted" style="margin-top: 20px;">
            <template #header>
              <h3 style="margin: 0;">⚠️ Confirmez la suppression</h3>
            </template>
            
            <el-descriptions :column="1" border style="margin-bottom: 20px;">
              <el-descriptions-item label="ID">{{ employe.id }}</el-descriptions-item>
              <el-descriptions-item label="Prénom">{{ employe.prenom }}</el-descriptions-item>
              <el-descriptions-item label="Nom">{{ employe.nom }}</el-descriptions-item>
              <el-descriptions-item label="Email">{{ employe.mail }}</el-descriptions-item>
              <el-descriptions-item label="Adresse">{{ employe.adresse }}</el-descriptions-item>
            </el-descriptions>
            
            <el-alert
              title="Êtes-vous sûr de vouloir supprimer définitivement cet employé ?"
              type="error"
              show-icon
              :closable="false"
              style="margin-bottom: 20px;"
            />
            
            <div style="text-align: center;">
              <el-space>
                <el-popconfirm
                  title="Confirmer la suppression définitive ?"
                  confirm-button-text="Oui, supprimer"
                  cancel-button-text="Annuler"
                  confirm-button-type="danger"
                  @confirm="confirmDelete"
                >
                  <template #reference>
                    <el-button 
                      type="danger" 
                      :loading="deleting"
                      :icon="Delete"
                    >
                      {{ deleting ? 'Suppression...' : 'Supprimer définitivement' }}
                    </el-button>
                  </template>
                </el-popconfirm>
                <el-button @click="cancelDelete">
                  Annuler
                </el-button>
              </el-space>
            </div>
          </el-card>

          <div style="margin-top: 30px; text-align: center;">
            <el-space>
              <el-button 
                type="success" 
                :icon="ArrowLeft"
                @click="$router.push('/front/')"
              >
                Retour au menu principal
              </el-button>
              <el-button 
                type="info" 
                :icon="List"
                @click="$router.push('/front/employes')"
              >
                Voir tous les employés
              </el-button>
            </el-space>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { getEmploye, deleteEmploye } from '../services/api';
import { Delete, ArrowLeft, List } from '@element-plus/icons-vue';

export default {
  name: 'EmployeDelete',
  components: {
    Delete,
    ArrowLeft,
    List
  },
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