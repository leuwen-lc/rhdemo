import { reactive } from 'vue';
import { getUserInfo } from '../services/api';

const userStore = reactive({
  username: '',
  roles: [],
  isLoaded: false
});

export function hasRole(role) {
  return userStore.roles.includes('ROLE_' + role);
}

export async function loadUserInfo() {
  try {
    const response = await getUserInfo();
    userStore.username = response.data.username;
    userStore.roles = response.data.roles;
    userStore.isLoaded = true;
  } catch (err) {
    console.error('Erreur lors du chargement des informations utilisateur', err);
  }
}

export default userStore;
