<script setup>
import { RouterView } from 'vue-router'
import TheSidebar from '@/components/layout/TheSidebar.vue'
</script>

<template>
  <div class="app-layout">
    <TheSidebar />
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  background-color: #f7fafc;
}

.main-content {
  flex-grow: 1;
  padding: 2.5rem;
  overflow-y: auto;
}
</style>