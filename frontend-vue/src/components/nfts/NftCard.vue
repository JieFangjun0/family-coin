<script setup>
import { ref, computed } from 'vue'
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

// --- 新增: 内部折叠状态，默认折叠 ---
const isCollapsed = ref(true)

function toggleCollapse() {
  if (props.context === 'collection') {
    isCollapsed.value = !isCollapsed.value
  }
}
// -----------------------------


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
  <div class="nft-card" :class="{ 'is-collapsed': isCollapsed }">
    <header 
        class="card-header" 
        @click="toggleCollapse"
        :class="{ 'clickable': context === 'collection' }"
    >
      <div class="summary-content">
        <component 
          :is="rendererComponent" 
          :nft="nft" 
          :context="context"
          :collapsed="true"
          @action="onAction" 
        >
            <template #summary="{ summary }">
                <div v-html="summary"></div> 
            </template>
        </component>
      </div>

      <div class="header-actions">
        <button 
          v-if="context === 'collection'" 
          class="toggle-button"
        >
          <span v-if="isCollapsed">展开 ▼</span>
          <span v-else>收起 ▲</span>
        </button>

        <button 
          v-if="context === 'collection' && nft.status === 'ACTIVE'" 
          @click.stop="onAction('destroy', {})" 
          class="destroy-button-icon"
          title="销毁此物品"
        >
          🔥
        </button>
      </div>
    </header>
    <div v-if="!isCollapsed" class="card-body">
        <component 
            :is="rendererComponent" 
            :nft="nft" 
            :context="context"
            :collapsed="false"
            @action="onAction" 
        />
    </div>
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

/* --- 新增样式：可折叠头部 --- */
.card-header {
  padding: 1rem 1.25rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e2e8f0;
  background-color: #f7fafc;
}

.card-header.clickable {
  cursor: pointer;
  transition: background-color 0.2s;
}

.card-header.clickable:hover {
  background-color: #edf2f7;
}

/* 仅当有 body 时才保留 bottom border */
/* 核心修复: 当折叠时，移除底部边框 */
.is-collapsed .card-header {
  border-bottom: none; 
}

.summary-content {
  flex-grow: 1;
  min-width: 0; /* 确保内容不会溢出 */
}

.header-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-shrink: 0; /* 防止动作按钮被压缩 */
}

.toggle-button {
  background-color: #42b883;
  color: white;
  border: none;
  padding: 0.5rem 0.8rem;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.2s;
}
.toggle-button:hover {
    background-color: #369b6e;
}

.destroy-button-icon {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0.2rem;
  line-height: 1;
  color: #c53030;
  transition: transform 0.1s;
}
.destroy-button-icon:hover {
  transform: scale(1.1);
  color: #9b2c2c;
}

.card-body {
    padding: 0;
}
/* 移除旧的 footer 样式，因为它不再需要 */
</style>