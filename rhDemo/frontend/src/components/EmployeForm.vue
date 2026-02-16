<template>
  <div>
    <el-row justify="center">
      <el-col :xs="24" :sm="18" :md="12" :lg="10">
        <el-card>
          <template #header>
            <h2 style="text-align: center; margin: 0;">
              {{ isEditing ? "✏️ Modification" : "➕ Ajout" }} d'un Employé
            </h2>
          </template>
          
          <el-loading-parent v-loading="loading">
            <el-form 
              v-if="!loading"
              :model="localEmploye"
              :rules="rules"
              ref="employeForm"
              label-position="top"
              @submit.prevent="submit"
            >
              <el-form-item label="Prénom" prop="prenom">
                <el-input
                  v-model="localEmploye.prenom"
                  placeholder="Prénom de l'employé"
                  data-testid="employe-prenom-input"
                />
              </el-form-item>
              
              <el-form-item label="Nom" prop="nom">
                <el-input
                  v-model="localEmploye.nom"
                  placeholder="Nom de l'employé"
                  data-testid="employe-nom-input"
                />
              </el-form-item>
              
              <el-form-item label="Email" prop="mail">
                <el-input
                  v-model="localEmploye.mail"
                  type="email"
                  placeholder="email@exemple.com"
                  data-testid="employe-email-input"
                />
              </el-form-item>
              
              <el-form-item label="Adresse (optionnelle)" prop="adresse">
                <el-input
                  v-model="localEmploye.adresse"
                  type="textarea"
                  placeholder="Adresse complète (optionnelle)"
                  :rows="3"
                  data-testid="employe-adresse-input"
                />
              </el-form-item>
              
              <el-form-item>
                <el-row justify="center">
                  <el-col :span="24" style="text-align: center;">
                    <el-space>
                      <el-tooltip
                        :disabled="canEdit"
                        content="Droits insuffisants"
                        placement="top"
                      >
                        <el-button
                          type="primary"
                          :loading="saving"
                          :disabled="!canEdit"
                          @click="submit"
                          data-testid="employe-submit-button"
                        >
                          {{ saving ? 'Sauvegarde...' : (isEditing ? 'Modifier' : 'Ajouter') }}
                        </el-button>
                      </el-tooltip>
                      <el-button 
                        @click="cancel"
                        data-testid="employe-cancel-button"
                      >
                        Annuler
                      </el-button>
                    </el-space>
                  </el-col>
                </el-row>
              </el-form-item>
            </el-form>
          </el-loading-parent>
          
          <el-alert
            v-if="error"
            :title="error"
            type="error"
            show-icon
            style="margin-top: 20px;"
            data-testid="employe-error-alert"
          />
          
          <el-alert
            v-if="success"
            :title="success"
            type="success"
            show-icon
            style="margin-top: 20px;"
            data-testid="employe-success-alert"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
<script>
import { getEmploye, saveEmploye } from '../services/api';
import { hasRole } from '../stores/userStore';

export default {
  name: 'EmployeForm',
  data() {
    return {
      localEmploye: {
        prenom: "",
        nom: "",
        mail: "",
        adresse: "",
        id: null
      },
      loading: false,
      saving: false,
      error: "",
      success: "",
      rules: {
        prenom: [
          { required: true, message: 'Le prénom est requis', trigger: 'blur' }
        ],
        nom: [
          { required: true, message: 'Le nom est requis', trigger: 'blur' }
        ],
        mail: [
          { required: true, message: 'L\'email est requis', trigger: 'blur' },
          { type: 'email', message: 'Format d\'email invalide', trigger: 'blur' }
        ],
        adresse: []  // Adresse optionnelle pour tous les cas
      }
    };
  },
  computed: {
    isEditing() {
      return !!this.$route.params.id;
    },
    canEdit() {
      return hasRole('MAJ');
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
        } catch (e) {
        this.error = "Erreur lors du chargement de l'employé";
        console.error('Erreur de chargement:', e);
      } finally {
        this.loading = false;
      }
    },
    
    async submit() {
      // Valider le formulaire
      const valid = await this.$refs.employeForm.validate().catch(() => false);
      if (!valid) return;
      
      this.saving = true;
      this.error = "";
      this.success = "";
      
      try {
        const employeToSave = { ...this.localEmploye };
        // Si l'adresse est vide, envoyer une chaîne vide ou null (selon l'API backend)
        if (!employeToSave.adresse) {
          employeToSave.adresse = '';
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