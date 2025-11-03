<script setup>
import { reactive, computed, ref, onUnmounted, onMounted } from 'vue'

const props = defineProps({
  nft: { type: Object, required: true },
  context: { type: String, default: 'collection' }
})

const emit = defineEmits(['action'])

const form = reactive({
  description: props.nft.data?.description || '一个秘密愿望',
  price: 10.0
})

const now = ref(Date.now() / 1000)
let timer;

onMounted(() => {
  // 每秒更新一次时间，用于倒计时
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

function handleListForSale() {
  emit('action', 'list-for-sale', {
    description: form.description,
    price: form.price
  })
}

function handleDestroy() {
    emit('action', 'destroy', {})
}

</script>

<template>
    <div class="nft-header">
      <span class="nft-type">SECRET_WISH</span>
      <h3 class="nft-name">{{ nft.data?.description || '[无描述]' }}</h3>
    </div>

    <ul class="nft-data" v-if="nft.data">
        <li><strong>ID:</strong> <code>{{ nft.nft_id?.substring(0, 8) }}...</code></li>
        <li><strong>创建者:</strong> {{ nft.data.creator_username || 'N/A' }}</li>
        <li v-if="context === 'collection' && !isExpired"><strong>秘密内容:</strong> <code>{{ nft.data.content || 'N/A' }}</code></li>
        <li class="countdown"><strong>⏳ {{ isExpired ? '已于' : '剩余' }}:</strong> {{ isExpired ? formatTimestamp(nft.data.destroy_timestamp) : countdownStr }}</li>
    </ul>
    <div v-else class="nft-data-error">[数据加载失败]</div>
    
    <template v-if="context === 'collection' && nft.data">
      <div v-if="isExpired" class="action-form">
        <h4>✨ 让它彻底消失</h4>
        <p class="help-text">这个愿望已经随着时间消散了。点击下方按钮可将其从你的收藏中永久移除。</p>
        <button class="destroy-button" @click="handleDestroy">确认销毁</button>
      </div>

      <form v-else class="action-form sell-form" @submit.prevent="handleListForSale">
        <h4>🛒 上架出售</h4>
        <div class="form-group"><label>描述</label><input type="text" v-model="form.description" required /></div>
        <div class="form-group"><label>价格 (FC)</label><input type="number" v-model.number="form.price" min="0.01" step="0.01" required /></div>
        <button type="submit">确认上架</button>
      </form>
    </template>
</template>

<style scoped>
.nft-header, .nft-data, .action-form { padding: 1rem 1.25rem; }
.nft-header { border-bottom: 1px solid #e2e8f0; }
.action-form { border-top: 1px solid #f0f2f5; }
.sell-form { background: #f7fafc; }
h3, h4 { margin: 0; margin-bottom: 0.75rem; }
h4 { font-size: 1rem; }
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
.destroy-button { background-color: #f56565; }
.destroy-button:hover { background-color: #e53e3e; }
.nft-type { background-color: #e2e8f0; color: #4a5568; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.nft-data-error { color: #c53030; font-style: italic; padding: 1rem 1.25rem; }
.help-text { font-size: 0.8rem; color: #718096; margin-top: -0.5rem; margin-bottom: 0.75rem;}
</style>