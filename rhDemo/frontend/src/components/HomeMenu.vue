<template>
  <div>
    <el-row justify="center">
      <el-col :span="20">
        <h2 style="text-align: center; margin-bottom: 30px;">Menu Principal - Gestion des Employés</h2>
        <el-row :gutter="20">
          <el-col :xs="24" :sm="8" :md="8">
            <el-card header="Consultation" class="menu-card">
              <div class="menu-buttons">
                <el-button
                  type="primary"
                  :icon="Document"
                  class="menu-button"
                  @click="$router.push('/front/employes')"
                >
                  Voir tous les employés
                </el-button>
                <el-button
                  type="primary"
                  :icon="Search"
                  class="menu-button"
                  @click="$router.push('/front/recherche')"
                >
                  Rechercher un employé par ID
                </el-button>
              </div>
            </el-card>
          </el-col>

          <el-col :xs="24" :sm="8" :md="8">
            <el-card header="Gestion" class="menu-card">
              <div class="menu-buttons">
                <el-tooltip
                  :disabled="canEdit"
                  content="Droits insuffisants"
                  placement="top"
                >
                  <el-button
                    type="success"
                    :icon="Plus"
                    class="menu-button"
                    :disabled="!canEdit"
                    @click="$router.push('/front/ajout')"
                  >
                    Ajouter un nouvel employé
                  </el-button>
                </el-tooltip>
                <el-tooltip
                  :disabled="canEdit"
                  content="Droits insuffisants"
                  placement="top"
                >
                  <el-button
                    type="danger"
                    :icon="Delete"
                    class="menu-button"
                    :disabled="!canEdit"
                    @click="$router.push('/front/suppression')"
                  >
                    Supprimer un employé par ID
                  </el-button>
                </el-tooltip>
              </div>
            </el-card>
          </el-col>

          <el-col :xs="24" :sm="8" :md="8">
            <el-card header="Modification" class="menu-card">
              <div class="menu-buttons">
                <el-tooltip
                  :disabled="canEdit"
                  content="Droits insuffisants"
                  placement="top"
                >
                  <el-button
                    type="warning"
                    :icon="Edit"
                    class="menu-button"
                    :disabled="!canEdit"
                    @click="$router.push('/front/modification')"
                  >
                    Modifier un employé par ID
                  </el-button>
                </el-tooltip>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { Document, Search, Plus, Delete, Edit } from '@element-plus/icons-vue';
import { hasRole } from '../stores/userStore';

export default {
  name: 'HomeMenu',
  components: {
    Document,
    Search,
    Plus,
    Delete,
    Edit
  },
  computed: {
    canEdit() {
      return hasRole('MAJ');
    }
  }
};
</script>

<style scoped>
.menu-card {
  margin-bottom: 20px;
  min-height: 200px;
}

.menu-buttons {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.menu-button {
  width: 100%;
  height: 50px;
  margin: 0 !important;
  padding-left: 20px !important;
  padding-right: 20px !important;
}

</style>
