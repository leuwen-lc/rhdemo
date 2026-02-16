<template>
  <div>
    <el-row justify="center">
      <el-col :xs="24" :sm="18" :md="12" :lg="10">
        <el-loading-parent v-loading="loading">
          <el-alert
            v-if="error"
            :title="error"
            type="error"
            show-icon
            style="margin-bottom: 20px;"
          />
          
          <el-card v-if="employe">
            <template #header>
              <h2 style="text-align: center; margin: 0;">
                👤 {{ employe.prenom }} {{ employe.nom }}
              </h2>
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
                    type="warning"
                    :icon="Edit"
                    :disabled="!canEdit"
                    @click="$router.push(`/front/edition/${employe.id}`)"
                  >
                    Modifier
                  </el-button>
                </el-tooltip>
                <el-button 
                  type="success" 
                  :icon="ArrowLeft"
                  @click="$router.push('/front/employes')"
                >
                  Retour à la liste
                </el-button>
              </el-space>
            </div>
          </el-card>
        </el-loading-parent>
      </el-col>
    </el-row>
  </div>
</template>
<script>
import { getEmploye } from '../services/api';
import { Edit, ArrowLeft } from '@element-plus/icons-vue';
import { hasRole } from '../stores/userStore';

export default {
  components: {
    Edit,
    ArrowLeft
  },
  computed: {
    canEdit() {
      return hasRole('MAJ');
    }
  },
  data() {
    return {
      employe: null,
      loading: false,
      error: ''
    };
  },
  async created() {
    this.loading = true;
    try {
      const res = await getEmploye(this.$route.params.id);
      this.employe = res.data;
    } catch (e) {
      this.error = 'Erreur de chargement';
    } finally {
      this.loading = false;
    }
  }
};
</script>