<script setup>
import { reactive, computed } from 'vue'

const props = defineProps({
  nft: { type: Object, required: true },
  context: { type: String, default: 'collection' }
})

const emit = defineEmits(['action'])

// +++ 修复请求 3：添加中文映射 +++
const ANOMALY_NAMES = {
  "GEO_ACTIVITY": "异常地质活动",
  "HIGH_ENERGY": "高频能量读数",
  "BIO_SIGN": "微弱的生命信号",
  "RHYTHMIC_PULSE": "有节律的电磁脉冲"
}
// +++ 修复结束 +++

// *** 核心修改：重构表单状态 ***
const form = reactive({
  list: {
    description: `行星: ${props.nft.data?.custom_name || `未命名行星 (${props.nft.nft_id?.substring(0, 6)})`}`,
    price: 50.0,
    listing_type: 'SALE', // 新增
    auction_hours: 24     // 新增
  },
  rename: {
    newName: props.nft.data?.custom_name || ''
  },
  scan: {
    selectedAnomaly: props.nft.data?.anomalies?.[0] || null
  }
})

const displayName = computed(() => props.nft.data?.custom_name || `未命名行星 (${props.nft.nft_id?.substring(0, 6)})`)

// *** 核心修改：发送更丰富的 payload ***
function handleListForSale() {
  emit('action', 'list-for-sale', {
    description: form.list.description,
    price: form.list.price,
    listing_type: form.list.listing_type,
    auction_hours: form.list.listing_type === 'AUCTION' ? form.list.auction_hours : null
  })
}

function handleRename() {
  emit('action', 'rename', {
    new_name: form.rename.newName
  })
}

function handleScan() {
    // 假设后端 /nfts/action 里的 'scan' 动作会自动处理 5 FC 的扣款
    emit('action', 'scan', {
        anomaly: form.scan.selectedAnomaly
    })
}

</script>

<template>
  <div class="nft-header">
    <h3 class="nft-name">🪐 {{ displayName }}</h3>
  </div>

  <ul class="nft-data" v-if="nft.data">
      <li><strong>坐标:</strong> <code>{{ nft.data.galactic_coordinates || 'N/A' }}</code></li>
      <li><strong>稀有度:</strong> {{ nft.data.rarity_score?.total || 'N/A' }}</li>
      <li><strong>恒星类别:</strong> {{ nft.data.stellar_class || 'N/A' }}</li>
      <li><strong>星球类型:</strong> {{ nft.data.planet_type || 'N/A' }}</li>
      <li v-if="nft.data.unlocked_traits?.length"><strong>已揭示特质:</strong> {{ nft.data.unlocked_traits.join(', ') }}</li>
      <li v-if="nft.data.anomalies?.length" class="anomaly"><strong>未探明信号:</strong> {{ nft.data.anomalies.length }} 个</li>
  </ul>
  <div v-else class="nft-data-error">[数据加载失败]</div>
  
  <template v-if="context === 'collection' && nft.data">
    <div v-if="nft.data.anomalies?.length" class="action-form">
        <h4>🛰️ 扫描异常信号</h4>
        <p class="help-text">消耗 5.0 FC 进行深度扫描，可能会有惊人发现。</p>
        <form @submit.prevent="handleScan">
            <div class="form-group">
                <select v-model="form.scan.selectedAnomaly">
                    <option v-for="anomaly in nft.data.anomalies" :key="anomaly" :value="anomaly">
                        {{ ANOMALY_NAMES[anomaly] || anomaly }}
                    </option>
                    </select>
            </div>
            <button type="submit">🚀 启动扫描</button>
        </form>
    </div>

    <div class="action-form">
        <h4>✏️ 重命名星球</h4>
        <form @submit.prevent="handleRename">
            <div class="form-group">
                <input type="text" v-model="form.rename.newName" placeholder="输入新的星球名称" required maxlength="20" />
            </div>
            <button type="submit">确认命名</button>
        </form>
    </div>

    <div class="action-form sell-form">
      <h4>🛒 上架出售</h4>
      <form @submit.prevent="handleListForSale">
        <div class="form-group"><label>描述</label><input type="text" v-model="form.list.description" required /></div>
        <div class="form-group">
          <label>上架类型</label>
          <select v-model="form.list.listing_type">
            <option value="SALE">一口价</option>
            <option value="AUCTION">拍卖</option>
          </select>
        </div>
        <div class="form-group">
            <label>{{ form.list.listing_type === 'SALE' ? '价格 (FC)' : '起拍价 (FC)' }}</label>
            <input type="number" v-model.number="form.list.price" min="0.01" step="0.01" required />
        </div>
        <div class="form-group" v-if="form.list.listing_type === 'AUCTION'">
            <label>拍卖持续小时数</label>
            <input type="number" v-model.number="form.list.auction_hours" min="0.1" step="0.1" required />
        </div>
        <button type="submit">确认上架</button>
      </form>
    </div>
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
code { background-color: #edf2f7; padding: 0.2rem 0.4rem; border-radius: 4px; }
.anomaly strong { color: #dd6b20; }
.form-group { margin-bottom: 0.75rem; }
.form-group label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; }
input, select { width: 100%; padding: 0.5rem 0.75rem; border-radius: 6px; border: 1px solid #cbd5e0; box-sizing: border-box; }
button { width: 100%; padding: 0.75rem; font-weight: 600; background-color: #42b883; color: white; border: none; border-radius: 6px; cursor: pointer; }
.nft-type { background-color: #e2e8f0; color: #4a5568; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.nft-data-error { color: #c53030; font-style: italic; padding: 1rem 1.25rem; }
.help-text { font-size: 0.8rem; color: #718096; margin-top: -0.5rem; margin-bottom: 0.75rem;}
</style>