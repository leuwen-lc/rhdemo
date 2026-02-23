<template>
  <div id="app">
    <div class="app-header">
      <div class="user-info" v-if="userStore.isLoaded" data-testid="user-info">
        <span class="user-name" data-testid="user-name">{{ userStore.username }}</span>
        <el-tag
          :type="profileTagType"
          size="small"
          data-testid="user-profile"
        >
          {{ profileLabel }}
        </el-tag>
      </div>
      <el-tooltip content="Deconnexion" placement="bottom">
        <el-button
          type="danger"
          circle
          size="small"
          :icon="SwitchButton"
          data-testid="logout-button"
          @click="logout"
        />
      </el-tooltip>
    </div>
    <router-view />
  </div>
</template>

<script>
import { SwitchButton } from '@element-plus/icons-vue';
import userStore, { loadUserInfo, hasRole } from './stores/userStore';

export default {
  components: {
    SwitchButton
  },
  data() {
    return {
      userStore
    };
  },
  computed: {
    currentRoute() {
      return this.$route.path;
    },
    profileLabel() {
      if (hasRole('MAJ')) {
        return 'Mise à jour';
      }
      if (hasRole('consult')) {
        return 'Consultation';
      }
      return '';
    },
    profileTagType() {
      return hasRole('MAJ') ? 'success' : 'info';
    }
  },
  created() {
    loadUserInfo();
  },
  methods: {
    logout() {
      const csrfToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('XSRF-TOKEN='))
        ?.split('=')[1];

      const form = document.createElement('form');
      form.method = 'POST';
      form.action = '/logout';

      if (csrfToken) {
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = '_csrf';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);
      }

      document.body.appendChild(form);
      form.submit();
    }
  }
};
</script>

<style>
.app-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 6px 16px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}
</style>
