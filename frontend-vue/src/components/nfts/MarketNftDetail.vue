<script setup>
import { computed } from 'vue'
import { nftRendererRegistry, defaultRenderer } from './renderer-registry.js'

const props = defineProps({
  // 接收来自 /market/listings 接口的完整 item 对象
  item: {
    type: Object,
    required: true
  }
})

// 根据 item.nft_type 从注册表中查找对应的组件
const rendererComponent = computed(() => {
  return nftRendererRegistry[props.item.nft_type] || defaultRenderer
})

// 构造一个符合渲染器组件期望的 nft 对象
const nftForRenderer = computed(() => {
    return {
        nft_id: props.item.nft_id,
        nft_type: props.item.nft_type,
        data: props.item.nft_data,
        // ... 其他渲染器可能需要的字段可以从 item 中添加
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