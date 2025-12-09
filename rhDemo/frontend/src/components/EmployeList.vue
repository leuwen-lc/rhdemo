<template>
  <div>
    <el-row justify="center">
      <el-col :span="22">
        <h2 style="text-align: center; margin-bottom: 20px;">📋 Liste de tous les Employés</h2>
        
        <el-row justify="center" style="margin-bottom: 20px;">
          <el-col :span="12" style="text-align: center;">
            <el-space>
              <el-button 
                type="default" 
                :icon="HomeFilled" 
                @click="$router.push('/front')"
                data-testid="back-to-menu-button"
              >
                Retour au menu
              </el-button>
              <el-button 
                type="primary" 
                :icon="Plus" 
                @click="$router.push('/front/ajout')"
                data-testid="add-employe-button"
              >
                Ajouter un employé
              </el-button>
              <el-button 
                type="info" 
                :icon="Refresh" 
                @click="fetchEmployes"
                data-testid="refresh-button"
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
            data-testid="employes-table"
            @sort-change="handleSort"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="prenom" label="Prénom" sortable="custom" />
            <el-table-column prop="nom" label="Nom" sortable="custom" />
            <el-table-column prop="mail" label="Email" sortable="custom" />
            <el-table-column prop="adresse" label="Adresse" sortable="custom" />
            <el-table-column label="Actions" width="300">
              <template #default="scope">
                <el-space>
                  <el-button 
                    size="small" 
                    type="info" 
                    :icon="View"
                    @click="$router.push(`/front/employe/${scope.row.id}`)"
                    :data-testid="`view-button-${scope.row.id}`"
                  >
                    Voir
                  </el-button>
                  <el-button 
                    size="small" 
                    type="warning" 
                    :icon="Edit"
                    @click="edit(scope.row.id)"
                    :data-testid="`edit-button-${scope.row.id}`"
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
                        :data-testid="`delete-button-${scope.row.id}`"
                      >
                        Supprimer
                      </el-button>
                    </template>
                  </el-popconfirm>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
          
          <el-row justify="center" style="margin-top: 20px;" v-if="employes.length > 0">
            <div data-testid="pagination">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :page-sizes="[10, 20, 50, 100]"
                :total="totalElements"
                layout="total, sizes, prev, pager, next, jumper"
                @size-change="handleSizeChange"
                @current-change="handlePageChange"
                background
              />
            </div>
          </el-row>
          
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
import { getEmployesPage, deleteEmploye } from '../services/api';
import { Plus, Refresh, View, Edit, Delete, HomeFilled } from '@element-plus/icons-vue';

export default {
  components: {
    Plus,
    Refresh,
    View,
    Edit,
    Delete,
    HomeFilled
  },
  data() {
    return {
      employes: [],
      loading: false,
      error: '',
      currentPage: 1,
      pageSize: 20,
      totalElements: 0,
      sortField: null,
      sortOrder: 'ASC'
    };
  },
  methods: {
    async fetchEmployes() {
      this.loading = true;
      this.error = '';
      try {
        const res = await getEmployesPage(
          this.currentPage - 1,
          this.pageSize,
          this.sortField,
          this.sortOrder
        );
        this.employes = res.data.content;
        // Structure PagedModel (VIA_DTO) : les métadonnées sont dans res.data.page
        this.totalElements = res.data.page.totalElements;
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
    },
    handlePageChange(page) {
      this.currentPage = page;
      this.fetchEmployes();
    },
    handleSizeChange(size) {
      this.pageSize = size;
      this.currentPage = 1;
      this.fetchEmployes();
    },
    handleSort({ prop, order }) {
      // Element Plus renvoie : order = 'ascending', 'descending' ou null
      if (order) {
        this.sortField = prop;
        this.sortOrder = order === 'ascending' ? 'ASC' : 'DESC';
      } else {
        // Pas de tri (clic pour annuler le tri)
        this.sortField = null;
        this.sortOrder = 'ASC';
      }
      this.currentPage = 1; // Retour à la première page lors d'un tri
      this.fetchEmployes();
    }
  },
  created() {
    this.fetchEmployes();
  }
};
</script>