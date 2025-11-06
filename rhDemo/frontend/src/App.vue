<template>
  <div id="app">
    <router-view />  
  </div>
</template>

<script>
export default {
  computed: {
    currentRoute() {
      return this.$route.path;
    }
  }
};
</script>

<style>
</style>