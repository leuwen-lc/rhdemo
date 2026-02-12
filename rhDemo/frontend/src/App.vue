<template>
  <div id="app">
    <div class="app-header">
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

export default {
  components: {
    SwitchButton
  },
  computed: {
    currentRoute() {
      return this.$route.path;
    }
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
}
</style>
