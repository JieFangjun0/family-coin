<script setup>
import { computed } from 'vue'
import { nftRendererRegistry, defaultRenderer } from './renderer-registry.js'

const props = defineProps({
  item: {
    type: Object,
    required: true
  }
})

// 根据 item.nft_type 从注册表中查找对应的组件
const rendererComponent = computed(() => {
  // 我们需要的是 handler 对象中的 'component' 属性
  return (nftRendererRegistry[props.item.nft_type] || defaultRenderer).component
})

const nftForRenderer = computed(() => {
    return {
        nft_id: props.item.nft_id,
        nft_type: props.item.nft_type,
        data: props.item.nft_data,
    }
})
</script>

<template>
  <component 
    :is="rendererComponent" 
    :nft="nftForRenderer" 
    context="market" 
  />
</template>