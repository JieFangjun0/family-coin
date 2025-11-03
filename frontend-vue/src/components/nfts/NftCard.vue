<script setup>
import { computed } from 'vue'
import { nftRendererRegistry, defaultRenderer } from './renderer-registry.js'

const props = defineProps({
  nft: {
    type: Object,
    required: true
  },
  // 核心修正：确保 context 属性被接收
  context: {
    type: String,
    default: 'collection' // 'collection', 'market', 'profile'
  }
})

// 定义一个通用的 emit 函数，这样我们就不需要在模板中列出所有事件
const emit = defineEmits()

// 计算属性，根据 nft.nft_type 从注册表中查找对应的组件
const rendererComponent = computed(() => {
  return nftRendererRegistry[props.nft.nft_type] || defaultRenderer
})

// 通用事件处理器，它会捕获任何从子组件发出的事件，并附带上当前NFT对象，然后再次向上抛出。
function onAction(action, payload) {
  emit('action', { action, nft: props.nft, payload })
}
</script>

<template>
  <div class="nft-card">
    <component 
      :is="rendererComponent" 
      :nft="nft" 
      :context="context"
      @action="onAction" 
    />
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