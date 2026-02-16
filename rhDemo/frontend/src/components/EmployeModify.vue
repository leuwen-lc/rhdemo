<template>
  <div>
    <el-row justify="center">
      <el-col :xs="24" :sm="18" :md="12" :lg="10">
        <el-card>
          <template #header>
            <h2 style="text-align: center; margin: 0;">✏️ Modifier un Employé par ID</h2>
          </template>
          
          <!-- Étape 1: Recherche de l'employé -->
          <el-card v-if="!employeFound" class="search-card">
            <template #header>
              <h3 style="margin: 0;">🔍 Rechercher l'employé</h3>
            </template>
            
            <el-form @submit.prevent="searchEmployeToModify">
              <el-form-item label="ID de l'employé à modifier">
                <el-input
                  v-model="modifyId"
                  type="number"
                  placeholder="Entrez l'ID de l'employé"
                  @keyup.enter="searchEmployeToModify"
                >
                  <template #append>
                    <el-button 
                      type="primary" 
                      :loading="loading"
                      :disabled="!modifyId"
                      @click="searchEmployeToModify"
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
          
          <!-- Étape 2: Affichage et modification de l'employé trouvé -->
          <el-card v-if="employe" style="margin-top: 20px;">
            <template #header>
              <h3 style="margin: 0;">👤 Employé trouvé</h3>
            </template>
            
            <el-descriptions :column="1" border>
              <el-descriptions-item label="ID">{{ employe.id }}</el-descriptions-item>
              <el-descriptions-item label="Prénom">{{ employe.prenom }}</el-descriptions-item>
              <el-descriptions-item label="Nom">{{ employe.nom }}</el-descriptions-item>
              <el-descriptions-item label="Email">{{ employe.mail }}</el-descriptions-item>
              <el-descriptions-item label="Adresse">{{ employe.adresse }}</el-descriptions-item>
            </el-descriptions>
            
            <div style="margin-top: 20px; text-align: center;">
              <el-space>
                <el-tooltip
                  :disabled="canEdit"
                  content="Droits insuffisants"
                  placement="top"
                >
                  <el-button
                    type="primary"
                    :icon="Edit"
                    :disabled="!canEdit"
                    @click="$router.push(`/front/edition/${employe.id}`)"
                  >
                    Modifier cet employé
                  </el-button>
                </el-tooltip>
                <el-button 
                  type="info" 
                  :icon="View"
                  @click="$router.push(`/front/employe/${employe.id}`)"
                >
                  Voir les détails
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
import { getEmploye } from '../services/api';
import { Edit, View, ArrowLeft, List } from '@element-plus/icons-vue';
import { hasRole } from '../stores/userStore';

export default {
  name: 'EmployeModify',
  components: {
    Edit,
    View,
    ArrowLeft,
    List
  },
  computed: {
    canEdit() {
      return hasRole('MAJ');
    }
  },
  data() {
    return {
      modifyId: '',
      employe: null,
      employeFound: false,
      loading: false,
      error: ''
    };
  },
  computed: {
    employeFound() {
      return !!this.employe;
    }
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