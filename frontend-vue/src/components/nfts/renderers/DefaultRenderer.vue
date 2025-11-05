<script setup>
import { computed } from 'vue'

const props = defineProps({
  nft: {
    type: Object,
    required: true
  },
  // --- 新增 prop ---
  collapsed: { type: Boolean, default: false }
  // --- 新增结束 ---
})
// 这个备用组件不提供上架功能

const summaryHtml = computed(() => {
    return `
        <div class="summary-wrapper">
            <span class="nft-type-unknown">未知类型</span>
            <span class="nft-title">${props.nft.nft_type} (${props.nft.nft_id?.substring(0, 8)})</span>
        </div>
    `
})
</script>

<script>
// 必须放在常规 <script> 块中才能具名导出
export function getSearchableText(data) {
  // 默认渲染器只依赖 MyCollectionView 中的通用搜索
  return ''; 
}
</script>

<template>
  <template v-if="collapsed">
    <slot name="summary" :summary="summaryHtml"></slot>
  </template>

  <template v-else>
    <div class="nft-header">
        <span class="nft-type-unknown">{{ nft.nft_type }}</span>
        <h3 class="nft-name">未知类型的 藏品</h3>
    </div>
    <div class="nft-data">
        <p>没有找到该类型的专属渲染器。以下是它的原始数据：</p>
        <pre>{{ JSON.stringify(nft.data, null, 2) }}</pre>
    </div>
  </template>
</template>

<style scoped>
.nft-header, .nft-data { padding: 1.25rem; }
.nft-header { border-bottom: 1px solid #e2e8f0; }
.nft-type-unknown {
  background-color: #fed7d7; color: #c53030; padding: 0.2rem 0.6rem;
  border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
}
.nft-name { margin-top: 0.75rem; }
pre {
  background-color: #f7fafc;
  padding: 1rem;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 0.8rem;
}

/* --- Summary 内部样式 (保持不变) --- */
.summary-wrapper {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.nft-type-unknown { /* 重用原有标签样式 */
    flex-shrink: 0;
}
.nft-title {
    font-size: 1.0rem;
    font-weight: 600;
    color: #2d3748;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}
/* --- 样式结束 --- */
</style>