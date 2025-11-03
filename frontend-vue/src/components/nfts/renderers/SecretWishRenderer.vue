<script setup>
import { reactive, computed } from 'vue'
import { formatTimestamp } from '@/utils/formatters'

const props = defineProps({
  nft: { type: Object, required: true },
  context: { type: String, default: 'collection' }
})

const emit = defineEmits(['list-for-sale'])

const form = reactive({
  description: props.nft.data?.description || '一个秘密愿望',
  price: 10.0
})

function handleListForSale() {
  emit('list-for-sale', {
    nft: props.nft,
    description: form.description,
    price: form.price
  })
}

// 使用计算属性来安全地计算剩余时间
const countdownStr = computed(() => {
    if (!props.nft.data?.destroy_timestamp) {
        return '未知';
    }
    const now = Date.now() / 1000
    const timeLeftSeconds = Math.max(0, props.nft.data.destroy_timestamp - now)
    const days = Math.floor(timeLeftSeconds / 86400)
    const hours = Math.floor((timeLeftSeconds % 86400) / 3600)
    const minutes = Math.floor((timeLeftSeconds % 3600) / 60)
    return `${days}天 ${hours}小时 ${minutes}分钟`
})
</script>

<template>
  <template v-if="context === 'collection'">
    <div class="nft-header">
      <span class="nft-type">SECRET_WISH</span>
      <h3 class="nft-name">{{ nft.data?.description || '[无描述]' }}</h3>
    </div>
    <ul class="nft-data" v-if="nft.data">
      <li><strong>ID:</strong> {{ nft.nft_id?.substring(0, 8) }}...</li>
      <li><strong>创建者:</strong> {{ nft.data.creator_username || 'N/A' }}</li>
      <li><strong>秘密内容:</strong> <code>{{ nft.data.content || 'N/A' }}</code></li>
      <li class="countdown"><strong>⏳ 剩余:</strong> {{ countdownStr }}</li>
    </ul>
    <div v-else class="nft-data-error">[数据加载失败]</div>
    
    <form v-if="nft.data" class="sell-form" @submit.prevent="handleListForSale">
      <h4>上架出售</h4>
      <div class="form-group"><label>描述</label><input type="text" v-model="form.description" required /></div>
      <div class="form-group"><label>价格 (FC)</label><input type="number" v-model.number="form.price" min="0.01" step="0.01" required /></div>
      <button type="submit">确认上架</button>
    </form>
  </template>

  <template v-if="context === 'market'">
    <ul class="nft-data market-view" v-if="nft.data">
      <li><strong>ID:</strong> {{ nft.nft_id?.substring(0, 8) }}...</li>
      <li><strong>创建者:</strong> {{ nft.data.creator_username || 'N/A' }}</li>
      <li class="countdown"><strong>⏳ 剩余:</strong> {{ countdownStr }}</li>
    </ul>
     <div v-else class="nft-data-error market-view">[数据加载失败]</div>
  </template>
</template>

<style scoped>
/* ... 样式保持不变 ... */
.nft-header, .nft-data, .sell-form { padding: 1rem 1.25rem; }
.nft-data.market-view { padding-bottom: 1rem; }
.nft-header { border-bottom: 1px solid #e2e8f0; }
.sell-form { background: #f7fafc; border-top: 1px solid #e2e8f0; }
h3, h4 { margin: 0; }
.nft-name { margin-top: 0.75rem; font-size: 1.25rem; color: #2d3748; }
ul { list-style: none; padding: 0; margin: 0; flex-grow: 1; font-size: 0.9rem; color: #4a5568; }
li { margin-bottom: 0.5rem; }
li strong { color: #2d3748; }
.countdown strong { color: #c53030; }
code { background-color: #edf2f7; padding: 0.2rem 0.4rem; border-radius: 4px; }
.form-group { margin-bottom: 0.75rem; }
.form-group label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; }
input { width: 100%; padding: 0.5rem 0.75rem; border-radius: 6px; border: 1px solid #cbd5e0; box-sizing: border-box; }
button { width: 100%; padding: 0.75rem; font-weight: 600; background-color: #42b883; color: white; border: none; border-radius: 6px; cursor: pointer; }
.nft-type { background-color: #e2e8f0; color: #4a5568; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.nft-data-error { color: #c53030; font-style: italic; padding: 1rem 1.25rem; }
</style>