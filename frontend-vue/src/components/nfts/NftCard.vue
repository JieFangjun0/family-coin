<script setup>
import { computed } from 'vue'
import { nftRendererRegistry, defaultRenderer } from './renderer-registry.js'

const props = defineProps({
  nft: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['list-for-sale'])

// 计算属性，根据 nft.nft_type 从注册表中查找对应的组件
const rendererComponent = computed(() => {
  return nftRendererRegistry[props.nft.nft_type] || defaultRenderer
})

// 当子组件触犯 list-for-sale 事件时，此函数会捕获并再次向上抛出
function onListForSale(payload) {
  emit('list-for-sale', payload)
}
</script>

<template>
  <div class="nft-card">
    <component :is="rendererComponent" :nft="nft" @list-for-sale="onListForSale" />
  </div>
</template>

<style scoped>
.nft-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
}
</style>