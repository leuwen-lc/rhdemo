<template>
  <div>
    <div v-if="loading">Chargement...</div>
    <div v-if="error" style="color:red">{{ error }}</div>
    <div v-if="employe">
      <h2>{{ employe.prenom }} {{ employe.nom }}</h2>
      <p>Email : {{ employe.mail }}</p>
    </div>
  </div>
</template>
<script>
import { getEmploye } from '../services/api';
export default {
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