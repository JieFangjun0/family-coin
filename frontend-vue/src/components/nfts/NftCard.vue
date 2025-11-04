<script setup>
import { computed } from 'vue'
import { nftRendererRegistry, defaultRenderer } from './renderer-registry.js'

const props = defineProps({
  nft: {
    type: Object,
    required: true
  },
  context: {
    type: String,
    default: 'collection' // 'collection', 'market', 'profile'
  }
})

const emit = defineEmits(['action'])

const rendererComponent = computed(() => {
  return nftRendererRegistry[props.nft.nft_type] || defaultRenderer
})

function onAction(action, payload) {
  // +++ 核心修改 3：添加销毁确认 +++
  if (action === 'destroy') {
    if (!confirm('你确定要永久销毁这个 NFT 吗？此操作不可撤销！')) {
      return
    }
  }
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
    
    <footer v-if="context === 'collection' && nft.status === 'ACTIVE'" class="nft-card-footer">
      <button @click="onAction('destroy', {})" class="destroy-button">
        🔥 销毁此物品
      </button>
    </footer>
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

/* +++ 核心修改 3：为新按钮添加样式 +++ */
.nft-card-footer {
  padding: 0.75rem 1.25rem;
  background-color: #fff9f9;
  border-top: 1px dashed #fed7d7;
  margin-top: auto; /* 确保它总是在卡片底部 */
}

.destroy-button {
  width: 100%;
  padding: 0.6rem;
  background-color: #f56565;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  font-size: 0.9rem;
  transition: background-color 0.2s;
}
.destroy-button:hover {
  background-color: #c53030;
}
/* +++ 修改结束 +++ */
</style>