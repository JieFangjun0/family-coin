<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { formatTimestamp, formatCurrency } from '@/utils/formatters'
import { apiCall } from '@/api'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  nft: { type: Object, required: true },
  context: { type: String, default: 'collection' }, // 'collection', 'market', 'profile'
  collapsed: { type: Boolean, default: false }
})

const emit = defineEmits(['action'])
const authStore = useAuthStore()

// --- 经济配置 (从 bio_dna.py 复制) ---
const HARVEST_COOLDOWN_SECONDS = 1 * 3600; // 1 小时
const TRAIN_COST_PER_LEVEL = 5.0;
const XP_NEEDED_PER_LEVEL = 100;

// --- 响应式表单 ---
const form = reactive({
  list: {
    description: `灵宠: ${props.nft.data?.nickname || props.nft.data?.species_name}`,
    price: 50.0,
    listing_type: 'SALE',
    auction_hours: 24
  },
  rename: {
    newName: props.nft.data?.nickname || ''
  },
  breed: {
    selectedPartnerId: null,
    partners: [],
    isLoadingPartners: false
  }
})

// --- 计时器 (用于丰收和冷却) ---
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

// --- 计算属性 (用于UI展示) ---
const nftData = computed(() => props.nft.data || {})
const econ = computed(() => nftData.value.economic_stats || {})
const stats = computed(() => nftData.value.stats || {})
const genes = computed(() => nftData.value.genes || {})
const visible = computed(() => nftData.value.visible_traits || {})
const cooldowns = computed(() => nftData.value.cooldowns || {})

// 产出 (JPH)
const jph = computed(() => econ.value.total_jph || 0)
const last_harvest_time = computed(() => nftData.value.last_harvest_time || 0)
const next_harvest_time = computed(() => last_harvest_time.value + HARVEST_COOLDOWN_SECONDS)
const can_harvest = computed(() => jph.value > 0 && now.value > next_harvest_time.value)
const harvest_cooldown_str = computed(() => {
    if (jph.value <= 0) return '不可产出';
    const timeLeft = Math.max(0, next_harvest_time.value - now.value);
    if (timeLeft === 0) return '可以丰收';
    const minutes = Math.floor(timeLeft / 60)
    const seconds = Math.floor(timeLeft % 60)
    return `冷却中: ${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`
})

// 训练 (XP)
const level = computed(() => nftData.value.level || 1)
const xp = computed(() => nftData.value.xp || 0)
const xp_needed = computed(() => XP_NEEDED_PER_LEVEL * level.value)
const train_cost = computed(() => TRAIN_COST_PER_LEVEL * level.value)
const train_cooldown_left = computed(() => Math.max(0, (cooldowns.value.train_until || 0) - now.value))
const can_train = computed(() => train_cooldown_left.value === 0)

// 繁育 (Breed)
const breeds_left = computed(() => (nftData.value.breeding_limit || 0) - (nftData.value.breeding_count || 0))
const breed_cooldown_left = computed(() => Math.max(0, (cooldowns.value.breed_until || 0) - now.value))
const can_breed = computed(() => nftData.value.gender === 'Female' && breeds_left.value > 0 && breed_cooldown_left.value === 0)

// --- 摘要 (用于折叠时) ---
const summaryHtml = computed(() => {
    const name = nftData.value.nickname || '[未命名]';
    const species = nftData.value.species_name || '未知';
    const rarity = nftData.value.species_rarity || 'COMMON';
    
    const jphTag = jph.value > 0 ? `<span class="jph-tag">💰 ${jph.value.toFixed(2)} JPH</span>` : '';

    return `
        <div class="summary-wrapper">
            <span class="nft-type-tag" style="background-color: #f0fff4; color: #2f855a;">灵宠</span>
            <span class="nft-title">❤️ ${name}</span>
            <span class="nft-status rarity-${rarity.toLowerCase()}">${species} (Lvl.${level.value})</span>
            ${jphTag}
        </div>
    `
})

// --- 动作 ---
function handleListForSale() {
  emit('action', 'list-for-sale', {
    description: form.list.description,
    price: form.list.price,
    listing_type: form.list.listing_type,
    auction_hours: form.list.listing_type === 'AUCTION' ? form.list.auction_hours : null
  })
}
function handleRename() {
  emit('action', 'rename', { new_name: form.rename.newName })
}
function handleHarvest() {
  emit('action', 'harvest', {})
}
function handleTrain() {
  emit('action', 'train', {})
}
async function fetchCompatiblePartners() {
  if (form.breed.partners.length > 0) return; // 已经加载过了
  
  form.breed.isLoadingPartners = true;
  const [data, error] = await apiCall('GET', '/nfts/my', {
    params: { public_key: authStore.userInfo.publicKey }
  });
  
  if (data) {
    form.breed.partners = data.nfts.filter(nft => {
      const pData = nft.data || {};
      const pCooldowns = pData.cooldowns || {};
      const pBreedsLeft = (pData.breeding_limit || 0) - (pData.breeding_count || 0);
      
      return nft.nft_id !== props.nft.nft_id &&
             nft.nft_type === 'BIO_DNA' &&
             pData.species_name === nftData.value.species_name &&
             pData.gender === 'Male' &&
             pBreedsLeft > 0 &&
             (pCooldowns.breed_until || 0) < now.value;
    });
  }
  form.breed.isLoadingPartners = false;
}
function handleBreed() {
  if (!form.breed.selectedPartnerId) {
    alert("请选择一个伴侣进行繁育。");
    return;
  }
  emit('action', 'breed', { partner_nft_id: form.breed.selectedPartnerId })
}

</script>

<template>
    <template v-if="collapsed">
      <slot name="summary" :summary="summaryHtml"></slot>
    </template>
  
    <template v-else>
      <div class="nft-header">
        <h3 class="nft-name">
          ❤️ {{ nftData.nickname }}
          <span class="species-name">({{ nftData.species_name }})</span>
        </h3>
        <span :class="['nft-status', `rarity-${nftData.species_rarity?.toLowerCase()}`]">
          {{ nftData.species_rarity }}
        </span>
      </div>

      <div class="nft-data-grid">
        <div class="stat-group">
            <h4><span class="stat-icon">📈</span> 养成</h4>
            <ul>
                <li><strong>等级:</strong> {{ level }}</li>
                <li><strong>经验:</strong> {{ xp }} / {{ xp_needed }}</li>
                <li><strong>产出:</strong> 💰 {{ jph.toFixed(2) }} JCoin / 小时</li>
                <li><strong>性别:</strong> {{ nftData.gender }}</li>
                <li><strong>世代:</strong> G{{ nftData.generation }}</li>
                <li><strong>性格:</strong> {{ nftData.personality }}</li>
            </ul>
            <h4><span class="stat-icon">🧬</span> 基因</h4>
            <ul>
                <li><strong>颜色:</strong> {{ visible.color }} <code class="genes">({{ genes.COLOR?.join(', ') }})</code></li>
                <li><strong>花纹:</strong> {{ visible.pattern }} <code class="genes">({{ genes.PATTERN?.join(', ') }})</code></li>
                <li><strong>光环:</strong> {{ visible.aura }} <code class="genes">({{ genes.AURA?.join(', ') }})</code></li>
            </ul>
        </div>
        <div class="stat-group">
            <h4><span class="stat-icon">📊</span> 潜力</h4>
            <ul>
                <li><strong>活力 (Vit):</strong> {{ stats.vitality }}</li>
                <li><strong>精神 (Spi):</strong> {{ stats.spirit }}</li>
                <li><strong>敏捷 (Agi):</strong> {{ stats.agility }}</li>
                <li><strong>幸运 (Luk):</strong> {{ stats.luck }}</li>
            </ul>
            <h4><span class="stat-icon">❤️</span> 繁育</h4>
            <ul>
                <li><strong>剩余次数:</strong> {{ breeds_left }} / {{ nftData.breeding_limit }}</li>
                <li><strong>繁育冷却:</strong> {{ breed_cooldown_left > 0 ? `${Math.ceil(breed_cooldown_left / 60)} 分钟` : '准备就绪' }}</li>
            </ul>
        </div>
      </div>

      <div v-if="context === 'market' || context === 'profile'" class="action-form">
        <p class="help-text">在“我的收藏”页面可以与灵宠互动。</p>
      </div>

      <template v-if="context === 'collection' && nft.data">
        
        <div class="action-form harvest-form">
            <h4><span class="stat-icon">⛏️</span> 资源丰收</h4>
            <p class="help-text">收集该灵宠累积的 JCoin。冷却时间: 1 小时。</p>
            <form @submit.prevent="handleHarvest">
                <button type="submit" :disabled="!can_harvest">
                  {{ can_harvest ? `立即丰收 (产出: ${jph.toFixed(2)} JCoin/hr)` : harvest_cooldown_str }}
                </button>
            </form>
        </div>
        
        <div class="action-form">
            <h4><span class="stat-icon">🏋️</span> 灵宠训练</h4>
            <p class="help-text">消耗 {{ formatCurrency(train_cost) }} FC 进行一次训练，获得 {{ XP_NEEDED_PER_LEVEL / 4 }} XP。</p>
            <form @submit.prevent="handleTrain">
                <button type="submit" :disabled="!can_train">
                  {{ can_train ? `开始训练 (消耗 ${formatCurrency(train_cost)} FC)` : `训练冷却中 (${Math.ceil(train_cooldown_left/60)} 分钟)` }}
                </button>
            </form>
        </div>
        
        <div class="action-form breed-form" v-if="nftData.gender === 'Female'">
            <h4><span class="stat-icon">❤️</span> 灵宠繁育</h4>
            <p class="help-text">
                作为母亲，选择一只（同物种、非冷却中、有次数的）雄性灵宠进行繁育。
            </p>
            <form @submit.prevent="handleBreed" v-if="can_breed">
                <div class="form-group">
                    <label>选择伴侣 (雄性 {{ nftData.species_name }})</label>
                    <select v-model="form.breed.selectedPartnerId" @click="fetchCompatiblePartners" required>
                        <option :value="null" disabled>-- {{ form.breed.isLoadingPartners ? '加载中...' : '选择伴侣' }} --</option>
                        <option v-for="p in form.breed.partners" :key="p.nft_id" :value="p.nft_id">
                            {{ p.data.nickname }} (Lvl.{{ p.data.level }}, 剩余 {{ (p.data.breeding_limit || 0) - (p.data.breeding_count || 0) }} 次)
                        </option>
                         <option v-if="!form.breed.isLoadingPartners && form.breed.partners.length === 0" :value="null" disabled>
                            没有找到符合条件的伴侣
                        </option>
                    </select>
                </div>
                <button type="submit" :disabled="!form.breed.selectedPartnerId">确认繁育 (消耗双方1次次数)</button>
            </form>
            <div v-else class="cooldown-text">
                <p>繁育冷却中 ({{ Math.ceil(breed_cooldown_left / 60) }} 分钟)</p>
            </div>
        </div>

        <div class="action-form">
            <h4><span class="stat-icon">✏️</span> 重命名</h4>
            <form @submit.prevent="handleRename" class="rename-form">
                <div class="form-group">
                    <input type="text" v-model="form.rename.newName" placeholder="输入新的昵称" required maxlength="30" />
                </div>
                <button type="submit">确认命名</button>
            </form>
        </div>

        <div class="action-form sell-form">
          <h4><span class="stat-icon">🛒</span> 上架出售</h4>
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
</template>

<style scoped>
/* --- 摘要样式 (用于卡片折叠时) --- */
.summary-wrapper {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: nowrap;
    overflow: hidden;
}
.nft-type-tag {
    font-size: 0.75rem;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-weight: 600;
    flex-shrink: 0;
}
.nft-title {
    font-size: 1.0rem;
    font-weight: 600;
    color: #2d3748;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    flex-shrink: 1;
}
.nft-status {
    font-size: 0.85rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    flex-shrink: 0;
}
.jph-tag {
    font-size: 0.85rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    flex-shrink: 0;
    color: #2f855a;
    background-color: #c6f6d5;
}

/* --- 详细视图样式 --- */
.nft-header {
    padding: 1rem 1.25rem;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.nft-name {
    margin: 0;
    font-size: 1.25rem;
    color: #2d3748;
}
.species-name {
    font-size: 0.9rem;
    color: #718096;
    font-weight: 500;
    margin-left: 0.5rem;
}
.rarity-common { background-color: #e2e8f0; color: #4a5568; }
.rarity-uncommon { background-color: #c6f6d5; color: #2f855a; }
.rarity-rare { background-color: #bee3f8; color: #2c5282; }
.rarity-mythic { background: linear-gradient(45deg, #faf089, #f687b3); color: #975a16; }

.nft-data-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    padding: 1rem 1.25rem;
    font-size: 0.9rem;
}
.stat-group h4 {
    font-size: 1rem;
    color: #2d3748;
    margin: 0 0 0.75rem 0;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 0.5rem;
}
.stat-icon { display: inline-block; }
.stat-group ul {
    list-style: none;
    padding: 0;
    margin: 0;
}
.stat-group li {
    margin-bottom: 0.5rem;
    color: #4a5568;
}
.stat-group li strong {
    color: #2d3748;
    min-width: 60px;
    display: inline-block;
}
code.genes {
    font-size: 0.8rem;
    color: #718096;
}

/* --- 动作表单 --- */
.action-form {
    padding: 1rem 1.25rem;
    border-top: 1px solid #f0f2f5;
}
.sell-form { background: #f7fafc; }
.harvest-form { background: #f0fff4; }
.breed-form { background: #fff5f7; }
.action-form h4 {
    margin: 0 0 0.75rem 0;
    font-size: 1rem;
    color: #2d3748;
}
.help-text {
    font-size: 0.8rem;
    color: #718096;
    margin-top: -0.5rem;
    margin-bottom: 0.75rem;
}
.cooldown-text {
    font-size: 0.9rem;
    color: #a0aec0;
    text-align: center;
    padding: 1rem 0;
}
.form-group { margin-bottom: 0.75rem; }
.form-group label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; }
input, select { width: 100%; padding: 0.5rem 0.75rem; border-radius: 6px; border: 1px solid #cbd5e0; box-sizing: border-box; }
button { width: 100%; padding: 0.75rem; font-weight: 600; background-color: #42b883; color: white; border: none; border-radius: 6px; cursor: pointer; }
button:disabled { background-color: #a0aec0; cursor: not-allowed; }

.rename-form {
    display: flex;
    gap: 0.5rem;
}
.rename-form .form-group {
    flex-grow: 1;
    margin: 0;
}
.rename-form button {
    width: auto;
    flex-shrink: 0;
}
</style>