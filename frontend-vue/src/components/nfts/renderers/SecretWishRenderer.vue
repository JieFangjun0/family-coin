<script setup>
// ... (导入和 props/emit 保持不变)
import { reactive, computed, ref, onUnmounted, onMounted } from 'vue'
import { formatTimestamp } from '@/utils/formatters'

const props = defineProps({
  nft: { type: Object, required: true },
  context: { type: String, default: 'collection' },
  // --- 新增 prop ---
  collapsed: { type: Boolean, default: false }
  // --- 新增结束 ---
})

const emit = defineEmits(['action'])

// ... (form, countdownStr, isExpired 等计算属性和方法保持不变)
const form = reactive({
  list: {
    description: props.nft.data?.description || '一个秘密愿望',
    price: 10.0,
    listing_type: 'SALE', // 新增
    auction_hours: 24     // 新增
  },
  destroy: {}
})

const now = ref(Date.now() / 1000)
let timer;

onMounted(() => {
  timer = setInterval(() => {
    now.value = Date.now() / 1000
  }, 1000)
})

onUnmounted(() => {
  clearInterval(timer)
})

const isExpired = computed(() => {
    return now.value > (props.nft.data?.destroy_timestamp || 0)
})

const countdownStr = computed(() => {
    if (!props.nft.data?.destroy_timestamp) {
        return '未知';
    }
    const timeLeftSeconds = Math.max(0, props.nft.data.destroy_timestamp - now.value)
    if (timeLeftSeconds === 0) return '已到期'

    const days = Math.floor(timeLeftSeconds / 86400)
    const hours = Math.floor((timeLeftSeconds % 86400) / 3600)
    const minutes = Math.floor((timeLeftSeconds % 3600) / 60)
    const seconds = Math.floor(timeLeftSeconds % 60)
    
    if (days > 0) return `${days}天 ${hours}小时 ${minutes}分钟`
    return `${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`
})

const summaryHtml = computed(() => {
    const statusClass = isExpired.value ? 'status-expired' : 'status-active'
    const statusText = isExpired.value ? '已到期' : `剩余: ${countdownStr.value}`
    
    return `
        <div class="summary-wrapper">
            <span class="nft-type-tag">秘密愿望</span>
            <span class="nft-title">“${props.nft.data?.description || '[无描述]'}”</span>
            <span class="nft-status ${statusClass}">${statusText}</span>
        </div>
    `
})

function handleListForSale() {
  emit('action', 'list-for-sale', {
    description: form.list.description,
    price: form.list.price,
    listing_type: form.list.listing_type,
    auction_hours: form.list.listing_type === 'AUCTION' ? form.list.auction_hours : null
  })
}

function handleDestroy() {
    emit('action', 'destroy', {})
}

</script>

<script>
// 必须放在常规 <script> 块中才能具名导出
export function getSearchableText(data) {
  if (!data) return '';
  // 允许用户搜索自己的秘密内容（仅在收藏视图中）
  return [data.description, data.content].join(' ');
}
</script>

<template>
    <template v-if="collapsed">
      <slot name="summary" :summary="summaryHtml"></slot>
    </template>
  
    <template v-else>
      <div class="nft-header">
        <h3 class="nft-name">💌 {{ nft.data?.description || '[无描述]' }}</h3>
      </div>

      <ul class="nft-data" v-if="nft.data">
          <li><strong>ID:</strong> <code>{{ nft.nft_id?.substring(0, 8) }}...</code></li>
          <li><strong>创建者:</strong> {{ nft.data.creator_username || 'N/A' }}</li>
          
          <li v-if="context === 'collection' && !isExpired"><strong>秘密内容:</strong> <code class="secret-content">{{ nft.data.content || 'N/A' }}</code></li>
          <li v-else-if="!isExpired"><strong>秘密内容:</strong> <code>[仅所有者可见]</code></li>


          <li class="countdown-line"><strong>⏳ {{ isExpired ? '已于' : '剩余' }}:</strong> <span :class="{ 'status-expired': isExpired }">{{ isExpired ? formatTimestamp(nft.data.destroy_timestamp) : countdownStr }}</span></li>
      </ul>
      <div v-else class="nft-data-error">[数据加载失败]</div>
      
      <template v-if="context === 'collection' && nft.data">
        <div v-if="isExpired" class="action-form">
          <h4>✨ 让它彻底消失</h4>
          <p class="help-text">这个愿望已经随着时间消散了。它从数据层面看已无效，但需要你手动移除。</p>
          </div>

        <form v-else class="action-form sell-form" @submit.prevent="handleListForSale">
          <h4>🛒 上架出售</h4>
          <div class="form-group"><label>描述</label><input type="text" v-model="form.list.description" required /></div>
          <div class="form-group">
            <label>上架类型</label>
            <select v-model="form.list.listing_type">
              <option value="SALE">一口价</option>
              <option value="AUCTION">拍卖</option>
            </select>
          </div>
          <div class="form-group">
              <label>{{ form.list.listing_type === 'SALE' ? '价格 (JCoin)' : '起拍价 (JCoin)' }}</label>
              <input type="number" v-model.number="form.list.price" min="0.01" step="0.01" required />
          </div>
          <div class="form-group" v-if="form.list.listing_type === 'AUCTION'">
              <label>拍卖持续小时数</label>
              <input type="number" v-model.number="form.list.auction_hours" min="0.1" step="0.1" required />
          </div>
          <button type="submit">确认上架</button>
        </form>
      </template>
    </template>
</template>

<style scoped>
.nft-header, .nft-data, .action-form { padding: 1rem 1.25rem; }
.nft-header { border-bottom: 1px solid #e2e8f0; margin: 0; }
.action-form { border-top: 1px solid #f0f2f5; }
.sell-form { background: #f7fafc; }
h3, h4 { margin: 0; margin-bottom: 0.75rem; }
h4 { font-size: 1rem; }
.nft-name { margin-top: 0.75rem; font-size: 1.25rem; color: #2d3748; }
ul { list-style: none; padding: 0; margin: 0; flex-grow: 1; font-size: 0.9rem; color: #4a5568; }
li { margin-bottom: 0.5rem; }
li strong { color: #2d3748; }
.countdown-line span { font-weight: 600; }
.countdown-line span.status-expired { color: #c53030; }

code { background-color: #edf2f7; padding: 0.2rem 0.4rem; border-radius: 4px; }
.secret-content { font-family: monospace; font-size: 1em; }
.form-group { margin-bottom: 0.75rem; }
.form-group label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; }
input, select { width: 100%; padding: 0.5rem 0.75rem; border-radius: 6px; border: 1px solid #cbd5e0; box-sizing: border-box; }
button { width: 100%; padding: 0.75rem; font-weight: 600; background-color: #42b883; color: white; border: none; border-radius: 6px; cursor: pointer; }
.destroy-button { background-color: #f56565; }
.destroy-button:hover { background-color: #e53e3e; }
.nft-type { background-color: #e2e8f0; color: #4a5568; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.nft-data-error { color: #c53030; font-style: italic; padding: 1rem 1.25rem; }
.help-text { font-size: 0.8rem; color: #718096; margin-top: -0.5rem; margin-bottom: 0.75rem;}

/* --- Summary 内部样式 (保持不变) --- */
.summary-wrapper {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.nft-type-tag {
    font-size: 0.75rem;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-weight: 600;
    color: #975a16;
    background-color: #feebc8;
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
.nft-status {
    font-size: 0.8rem;
    font-weight: 500;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    flex-shrink: 0;
}
.nft-status.status-active {
    color: #2f855a;
    background-color: #c6f6d5;
}
.nft-status.status-expired {
    color: #c53030;
    background-color: #fed7d7;
}
</style>