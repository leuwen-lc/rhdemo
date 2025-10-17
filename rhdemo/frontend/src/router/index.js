import { createRouter, createWebHistory } from 'vue-router';
import HomeMenu from '../components/HomeMenu.vue';
import EmployeList from '../components/EmployeList.vue';
import EmployeDetail from '../components/EmployeDetail.vue';
import EmployeForm from '../components/EmployeForm.vue';
import EmployeSearch from '../components/EmployeSearch.vue';
import EmployeDelete from '../components/EmployeDelete.vue';
import EmployeModify from '../components/EmployeModify.vue';

const routes = [
  { path: '/front/', component: HomeMenu, name: 'home' },
  { path: '/front/employes', component: EmployeList, name: 'employe-list' },
  { path: '/front/employe/:id', component: EmployeDetail, props: true, name: 'employe-detail' },
  { path: '/front/ajout', component: EmployeForm, name: 'employe-add' },
  { path: '/front/edition/:id', component: EmployeForm, props: true, name: 'employe-edit' },
  { path: '/front/recherche', component: EmployeSearch, name: 'employe-search' },
  { path: '/front/suppression', component: EmployeDelete, name: 'employe-delete' },
  { path: '/front/modification', component: EmployeModify, name: 'employe-modify' },
  // Redirection de la racine vers le menu principal
  { path: '/', redirect: '/front/' }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;