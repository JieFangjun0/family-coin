<script setup>
import { RouterLink } from 'vue-router'

defineProps({
  uid: {
    type: String,
    required: true
  },
  username: {
    type: String,
    required: true
  }
})
</script>

<template>
  <RouterLink :to="{ name: 'community', params: { uid: uid } }" class="username-link" @click.stop>
    {{ username }}
  </RouterLink>
</template>

<style scoped>
.username-link {
  font-weight: 600;
  color: #42b883;
  text-decoration: none;
  transition: color 0.2s;
}
.username-link:hover {
  color: #369b6e;
  text-decoration: underline;
}
</style>