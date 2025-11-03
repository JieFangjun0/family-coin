<script setup>
import { reactive, computed } from 'vue'

const props = defineProps({
  nft: { type: Object, required: true },
  context: { type: String, default: 'collection' }
})

const emit = defineEmits(['list-for-sale'])

// 使用计算属性来安全地访问数据
const displayName = computed(() => props.nft.data?.custom_name || `未命名行星 (${props.nft.nft_id?.substring(0, 6)})`)

const form = reactive({
  description: `行星: ${displayName.value}`,
  price: 50.0
})

function handleListForSale() {
  emit('list-for-sale', {
    nft: props.nft,
    description: form.description,
    price: form.price
  })
}
</script>

<template>
    <template v-if="context === 'collection'">
        <div class="nft-header">
            <span class="nft-type">PLANET</span>
            <h3 class="nft-name">🪐 {{ displayName }}</h3>
        </div>
        <ul class="nft-data" v-if="nft.data">
            <li><strong>坐标:</strong> {{ nft.data.galactic_coordinates || 'N/A' }}</li>
            <li><strong>稀有度:</strong> {{ nft.data.rarity_score?.total || 'N/A' }}</li>
            <li><strong>恒星类别:</strong> {{ nft.data.stellar_class || 'N/A' }}</li>
            <li><strong>星球类型:</strong> {{ nft.data.planet_type || 'N/A' }}</li>
            <li v-if="nft.data.unlocked_traits?.length"><strong>已揭示特质:</strong> {{ nft.data.unlocked_traits.join(', ') }}</li>
            <li v-if="nft.data.anomalies?.length"><strong>未探明信号:</strong> {{ nft.data.anomalies.length }} 个</li>
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
            <li><strong>坐标:</strong> {{ nft.data.galactic_coordinates || 'N/A' }}</li>
            <li><strong>稀有度:</strong> {{ nft.data.rarity_score?.total || 'N/A' }}</li>
            <li><strong>恒星类别:</strong> {{ nft.data.stellar_class || 'N/A' }}</li>
            <li v-if="nft.data.unlocked_traits?.length"><strong>已揭示特质:</strong> {{ nft.data.unlocked_traits.join(', ') }}</li>
            <li v-if="nft.data.anomalies?.length"><strong>未探明信号:</strong> {{ nft.data.anomalies.length }} 个</li>
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
.form-group { margin-bottom: 0.75rem; }
.form-group label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; }
input { width: 100%; padding: 0.5rem 0.75rem; border-radius: 6px; border: 1px solid #cbd5e0; box-sizing: border-box; }
button { width: 100%; padding: 0.75rem; font-weight: 600; background-color: #42b883; color: white; border: none; border-radius: 6px; cursor: pointer; }
.nft-type { background-color: #e2e8f0; color: #4a5568; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.nft-data-error { color: #c53030; font-style: italic; padding: 1rem 1.25rem; }
</style>