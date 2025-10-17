<template>
  <div>
    <el-row justify="center">
      <el-col :xs="24" :sm="18" :md="12" :lg="10">
        <el-card>
          <template #header>
            <h2 style="text-align: center; margin: 0;">🔍 Rechercher un Employé par ID</h2>
          </template>
          
          <el-form @submit.prevent="searchEmploye">
            <el-form-item label="ID de l'employé">
              <el-input
                v-model="searchId"
                type="number"
                placeholder="Entrez l'ID de l'employé"
                @keyup.enter="searchEmploye"
              >
                <template #append>
                  <el-button 
                    type="primary" 
                    :loading="loading"
                    :disabled="!searchId"
                    @click="searchEmploye"
                  >
                    {{ loading ? 'Recherche...' : 'Rechercher' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-form>

          <el-alert
            v-if="error"
            :title="error"
            type="error"
            show-icon
            style="margin: 20px 0;"
          />
          
          <el-card v-if="employe" style="margin-top: 20px;">
            <template #header>
              <h3 style="margin: 0;">👤 Employé trouvé</h3>
            </template>
            
            <el-descriptions :column="1" border>
              <el-descriptions-item label="ID">{{ employe.id }}</el-descriptions-item>
              <el-descriptions-item label="Prénom">{{ employe.prenom }}</el-descriptions-item>
              <el-descriptions-item label="Nom">{{ employe.nom }}</el-descriptions-item>
              <el-descriptions-item label="Email">{{ employe.mail }}</el-descriptions-item>
            </el-descriptions>
            
            <div style="margin-top: 20px; text-align: center;">
              <el-space>
                <el-button 
                  type="primary" 
                  :icon="View"
                  @click="$router.push(`/front/employe/${employe.id}`)"
                >
                  Voir les détails
                </el-button>
                <el-button 
                  type="warning" 
                  :icon="Edit"
                  @click="$router.push(`/front/edition/${employe.id}`)"
                >
                  Modifier
                </el-button>
              </el-space>
            </div>
          </el-card>

          <div style="margin-top: 30px; text-align: center;">
            <el-button 
              type="success" 
              :icon="ArrowLeft"
              @click="$router.push('/front/')"
            >
              Retour au menu principal
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { getEmploye } from '../services/api';
import { View, Edit, ArrowLeft } from '@element-plus/icons-vue';

export default {
  name: 'EmployeSearch',
  components: {
    View,
    Edit,
    ArrowLeft
  },
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