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
  },
  // 接收局部反馈消息, 结构: { text: "...", type: "success" }
  localFeedbackMessage: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['action'])

const rendererComponent = computed(() => {
  // 从注册表获取 handler 对象
  const handler = nftRendererRegistry[props.nft.nft_type] || defaultRenderer;
  // 返回 handler 对象中的 'component' 属性
  return handler.component; 
})

// 内部折叠状态，默认折叠
const isCollapsed = ref(true)

function toggleCollapse() {
  // 仅在 'collection' 上下文中允许点击切换
  if (props.context === 'collection') {
    isCollapsed.value = !isCollapsed.value
  }
}

function onAction(action, payload) {
  // 添加销毁确认
  if (action === 'destroy') {
    if (!confirm('你确定要永久销毁这个 藏品 吗？此操作不可撤销！')) {
      return
    }
  }
  // 向父组件派发事件
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
        <!-- 渲染概要内容 -->
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
        <!-- 折叠/展开 按钮 -->
        <button 
          v-if="context === 'collection'" 
          class="toggle-button"
        >
          <span v-if="isCollapsed">展开 ▼</span>
          <span v-else>收起 ▲</span>
        </button>

        <!-- 销毁按钮 -->
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
    
    <!-- 卡片主体（可折叠） -->
    <div v-if="!isCollapsed" class="card-body">
        
      <!-- 局部反馈消息 -->
      <div 
        v-if="localFeedbackMessage" 
        :class="['local-feedback', localFeedbackMessage.type]"
      >
        {{ localFeedbackMessage.text }}
      </div>
      
      <!-- 渲染详细内容 -->
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
/* 折叠时移除头部底边框 */
.is-collapsed .card-header { 
  border-bottom: none; 
}
.summary-content { 
  flex-grow: 1; 
  min-width: 0; 
}
.header-actions { 
  display: flex; 
  gap: 0.75rem; 
  align-items: center; 
  flex-shrink: 0; 
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
  position: relative;
}

/* 局部反馈样式 */
.local-feedback {
  padding: 0.75rem 1.25rem;
  text-align: center;
  font-weight: 500;
  font-size: 0.9rem;
  animation: fadeIn 0.3s;
  /* 将其与渲染器内容分开 */
  border-bottom: 1px dashed #e2e8f0;
}
.local-feedback.success {
  color: #155724; 
  background-color: #d4edda;
}
.local-feedback.error {
  color: #d8000c; 
  background-color: #ffbaba;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>