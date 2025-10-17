<template>
  <div>
    <el-row justify="center">
      <el-col :span="22">
        <h2 style="text-align: center; margin-bottom: 20px;">📋 Liste de tous les Employés</h2>
        
        <el-row justify="center" style="margin-bottom: 20px;">
          <el-col :span="12" style="text-align: center;">
            <el-space>
              <el-button 
                type="primary" 
                :icon="Plus" 
                @click="$router.push('/front/ajout')"
              >
                Ajouter un employé
              </el-button>
              <el-button 
                type="info" 
                :icon="Refresh" 
                @click="fetchEmployes"
              >
                Actualiser
              </el-button>
            </el-space>
          </el-col>
        </el-row>
        
        <el-loading-parent v-loading="loading">
          <el-alert
            v-if="error"
            :title="error"
            type="error"
            show-icon
            style="margin-bottom: 20px;"
          />
          
          <el-table 
            v-if="employes.length > 0"
            :data="employes" 
            style="width: 100%"
            stripe
            border
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="prenom" label="Prénom" />
            <el-table-column prop="nom" label="Nom" />
            <el-table-column prop="mail" label="Email" />
            <el-table-column label="Actions" width="300">
              <template #default="scope">
                <el-space>
                  <el-button 
                    size="small" 
                    type="info" 
                    :icon="View"
                    @click="$router.push(`/front/employe/${scope.row.id}`)"
                  >
                    Voir
                  </el-button>
                  <el-button 
                    size="small" 
                    type="warning" 
                    :icon="Edit"
                    @click="edit(scope.row.id)"
                  >
                    Editer
                  </el-button>
                  <el-popconfirm
                    title="Êtes-vous sûr de vouloir supprimer cet employé ?"
                    @confirm="del(scope.row.id)"
                  >
                    <template #reference>
                      <el-button 
                        size="small" 
                        type="danger" 
                        :icon="Delete"
                      >
                        Supprimer
                      </el-button>
                    </template>
                  </el-popconfirm>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
          
          <el-empty 
            v-else-if="!loading && !error"
            description="Aucun employé trouvé"
          >
            <el-button 
              type="primary" 
              :icon="Plus"
              @click="$router.push('/front/ajout')"
            >
              Ajouter le premier employé
            </el-button>
          </el-empty>
        </el-loading-parent>
      </el-col>
    </el-row>
  </div>
</template>
<script>
import { getEmployes, deleteEmploye } from '../services/api';
import { Plus, Refresh, View, Edit, Delete } from '@element-plus/icons-vue';

export default {
  components: {
    Plus,
    Refresh,
    View,
    Edit,
    Delete
  },
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