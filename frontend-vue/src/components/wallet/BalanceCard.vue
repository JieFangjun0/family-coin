<script setup>
defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: [String, Number],
    required: false // <--- 核心修改 1: 变为 false
  },
  unit: {
    type: String,
    default: ''
  }
})
</script>

<template>
  <div class="balance-card">
    <span class="label">{{ label }}</span>
    
    <span v-if="value !== undefined" class="value">
      {{ value }} <span v-if="unit" class="unit">{{ unit }}</span>
    </span>
    <span v-else class="value">
      <slot></slot> </span>
    </div>
</template>

<style scoped>
.balance-card {
  background-color: #fff;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.label {
  display: block;
  font-size: 0.9rem;
  color: #718096;
  margin-bottom: 0.5rem;
}

.value {
  display: block;
  font-size: 2rem;
  font-weight: 600;
  color: #2d3748;
  
  /* +++ 核心修改 3: 确保插槽内容垂直居中 +++ */
  display: flex;
  align-items: center;
}

.unit {
  font-size: 1.25rem;
  font-weight: 500;
  color: #a0aec0;
  margin-left: 0.25rem;
}
</style>