<script setup>
import { reactive, computed, ref, onUnmounted, onMounted } from 'vue'
import { formatTimestamp, formatCurrency } from '@/utils/formatters'
import { useEconomicsStore } from '@/stores/economics.js'
import { apiCall } from '@/api'
const props = defineProps({
  nft: { type: Object, required: true },
  context: { type: String, default: 'collection' },
  collapsed: { type: Boolean, default: false }
})

const emit = defineEmits(['action'])

// --- V3: 经济配置 (从 Store 解耦) ---
const econStore = useEconomicsStore()
const planetEcon = computed(() => econStore.configs.PLANET || {})
const HARVEST_COOLDOWN_SECONDS = computed(() => planetEcon.value.HARVEST_COOLDOWN_SECONDS || 3600)
const SCAN_COST = computed(() => planetEcon.value.SCAN_COST || 10.0)

// --- 响应式表单 ---
const form = reactive({
  list: {
    description: `行星: ${props.nft.data?.custom_name || `未命名行星 (${props.nft.nft_id?.substring(0, 6)})`}`,
    price: 50.0,
    listing_type: 'SALE',
    auction_hours: 24
  },
  rename: {
    newName: props.nft.data?.custom_name || ''
  },
  scan: {
    selectedAnomaly: props.nft.data?.anomalies?.[0] || null
  }
})

// --- V3: JPH 实时轮询 ---
const accumulatedJph = ref(0.0)
const isReadyToHarvest = ref(false)
const cooldownLeftSeconds = ref(0)
let pollTimer = null;

async function pollJphStatus() {
  if (!props.nft || !props.nft.nft_id) return;
  
  // (仅当组件在屏幕上时才轮询 - 可选优化)
  // if (document.hidden) return; 

  const [data, error] = await apiCall('GET', `/nfts/${props.nft.nft_id}/jph_status`);
  if (data) {
    accumulatedJph.value = data.accumulated_jph;
    isReadyToHarvest.value = data.is_ready;
    cooldownLeftSeconds.value = data.cooldown_left_seconds;
  }
}

onMounted(() => {
  pollJphStatus(); // 立即调用一次
  pollTimer = setInterval(pollJphStatus, 30000); // 设置每 5 秒轮询
})

onUnmounted(() => {
  clearInterval(pollTimer); // 清除计时器
})

const nftData = computed(() => props.nft.data || {})
const economic_stats = computed(() => nftData.value.economic_stats || {})
const rarity_score = computed(() => nftData.value.rarity_score || {})


const unlockedTraitNames = computed(() => {
  if (!nftData.value.unlocked_traits?.length) {
    return []
  }
  // 注意：这里我们引用了外部 <script> 块中的 TRAIT_NAMES
  return nftData.value.unlocked_traits.map(traitId => TRAIT_NAMES[traitId] || traitId)
})

const jph = computed(() => economic_stats.value.total_jph || 0)

const harvest_cooldown_str = computed(() => {
    if (jph.value <= 0) return '不可开采';
    
    // 使用来自 API 的 isReadyToHarvest
    if (isReadyToHarvest.value) {
      return `可收获 (已积累: ${accumulatedJph.value.toFixed(4)} JCoin)`;
    }
    
    // 使用来自 API 的 cooldownLeftSeconds
    const timeLeftSeconds = cooldownLeftSeconds.value;
    if (timeLeftSeconds <= 0) return '正在计算...';

    const hours = Math.floor(timeLeftSeconds / 3600)
    const minutes = Math.floor((timeLeftSeconds % 3600) / 60)
    const seconds = Math.floor(timeLeftSeconds % 60)
    
    return `冷却中: ${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`
})
// --- V3 结束 ---


const displayName = computed(() => nftData.value.custom_name || `未命名行星 (${props.nft.nft_id?.substring(0, 6)})`)

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
    emit('action', 'scan', {
        anomaly: form.scan.selectedAnomaly
    })
}

// --- V3: 新增收获动作 ---
function handleHarvest() {
    emit('action', 'harvest', {})
}

// --- V3: 更新摘要 ---
const summaryHtml = computed(() => {
    const rarity = rarity_score.value.total || '未知';
    const name = displayName.value;
    const anomalies = nftData.value.anomalies?.length || 0;
    const currentJph = jph.value || 0;
    
    const anomalyTag = anomalies > 0 ? `<span class="anomaly-tag">+${anomalies} 信号</span>` : '';
    const jphTag = currentJph > 0 ? `<span class="jph-tag">💰 ${currentJph.toFixed(2)} JPH</span>` : '';

    return `
        <div class="summary-wrapper">
            <span class="nft-type-tag">星球</span>
            <span class="nft-title">🪐 ${name}</span>
            <span class="nft-status status-rarity">稀有度: ${rarity}</span>
            ${jphTag}
            ${anomalyTag}
        </div>
    `
})
</script>

<script>
// --- V3: 扩展的异常信号中文映射 ---
// (从 setup 移到这里)
const ANOMALY_NAMES = {
    "SIG_GEO_FLUX": "地质通量",
    "SIG_WEAK_ENERGY": "微弱能量读数",
    "SIG_FAINT_BIO": "模糊的生命信号",
    "SIG_HIGH_ENERGY": "高频能量读数",
    "SIG_COMPLEX_STRUCTURE": "复杂结构回波",
    "SIG_DEEP_SCAN": "深层回音",
    "SIG_OCEANIC_ANOMALY": "海洋异常",
    "SIG_RHYTHMIC_PULSE": "有节律的电磁脉冲",
    "SIG_PLANET_WIDE": "全球范围异常",
    // 向下兼容旧的
    "GEO_ACTIVITY": "异常地质活动",
    "HIGH_ENERGY": "高频能量读数",
    "BIO_SIGN": "微弱的生命信号",
    "RHYTHMIC_PULSE": "有节律的电磁脉冲"
}

// 添加特质中文映射 +++
const TRAIT_NAMES = {
    "RES_ZERO_POINT": "零点能量场",
    "RES_HEAVY_MINERAL": "超重力矿脉",
    "RES_DIAMOND_RAIN": "钻石雨",
    "RES_HELIUM_3": "氦-3富集",
    "RES_SPICE": "异星香料",
    "RES_ANTIMATTER": "反物质喷泉",
    "RES_ADAMANTIUM": "艾德曼合金矿",
    "RES_CRYONIUM": "氪冰矿",
    "LIFE_SILICON": "硅基生命痕迹",
    "LIFE_SENTIENT_PLANT": "感知植物群",
    "LIFE_GAS_WHALE": "气态巨兽",
    "LIFE_EXTREMEPHILE": "极端微生物",
    "LIFE_PARADISE": "生物天堂",
    "LIFE_KRAKEN": "深海巨妖",
    "ART_ANCIENT_RUINS": "远古外星遗物",
    "ART_SLEEPING_SHIP": "休眠的星际飞船",
    "ART_UNSTABLE_PORTAL": "不稳定的传送门",
    "ART_FORERUNNER_MAP": "先行者星图",
    "ART_WORLD_ENGINE": "世界引擎",
    "ART_DYSON_SPHERE_FRAG": "戴森球残片",
    "ART_ORACLE": "神谕AI",
    "WON_ETERNAL_STORM": "永恒风暴",
    "WON_NATURAL_PULSAR": "天然脉冲星",
    "WON_SKY_MIRROR": "天空之镜",
    "WON_FLOATING_ISLES": "悬浮岛屿",
    "WON_CRYSTAL_FOREST": "水晶森林",
    "WON_TIME_ANOMALY": "时间泡",
    "WON_GRAVITY_RIFT": "重力裂隙",
    "DUD_HIGH_RADIATION": "高强度辐射",
    "DUD_UNSTABLE_CRUST": "不稳定地壳",
    "DUD_TOXIC_ATMOS": "剧毒大气",
    "DUD_ROGUE_ASTEROIDS": "流氓小行星带",
    "DUD_ANCIENT_PLAGUE": "远古瘟疫",
    "DUD_VOID_ORGANISM": "虚空生物",
    "DUD_LOST_COLONY": "失落的殖民地",
    "DUD_NOTHING": "一无所获",
    "RES_WATER_ICE": "丰富的水冰",
    "RES_THOLINS": "泰坦有机S",
    "LIFE_FUNGAL_WASTES": "真菌荒原",
    "WON_AURORA": "强极光",
    "WON_GIANT_VOLCANO": "超级火山",
    "ART_CRASH_SITE": "飞船坠毁点",
    "DUD_BARREN": "贫瘠之地",
    "DUD_FALSE_ALARM": "虚假警报",
    "RES_SILICATES": "硅酸盐岩石",
    "WON_DEEP_CANYON": "大裂谷",
    "LIFE_BACTERIA": "细菌菌落",
    "ART_SATELLITE": "失控的人造卫星",
    "DUD_MAGNETIC_FIELD": "异常磁场",
    "RES_METHANE_LAKE": "甲烷湖",
}

// 必须放在常规 <script> 块中才能具名导出
export function getSearchableText(data) {
  if (!data) return '';
  const traits = (data.unlocked_traits || []).map(id => TRAIT_NAMES[id] || '');
  const anomalies = (data.anomalies || []).map(id => ANOMALY_NAMES[id] || '');
  return [
    data.planet_type, 
    data.stellar_class, 
    data.custom_name, 
    ...traits, 
    ...anomalies
  ].join(' ');
}
</script>

<template>
    <template v-if="collapsed">
      <slot name="summary" :summary="summaryHtml"></slot>
    </template>
  
    <template v-else>
      <div class="nft-header">
        <h3 class="nft-name">🪐 {{ displayName }}</h3>
      </div>

      <ul class="nft-data" v-if="nft.data">
          <li><strong>坐标:</strong> <code>{{ nftData.galactic_coordinates || 'N/A' }}</code></li>
          <li><strong>稀有度:</strong> {{ rarity_score.total || 'N/A' }} (基础: {{ rarity_score.base }}, 特质: {{ rarity_score.traits }})</li>
          <li><strong>恒星类别:</strong> {{ nftData.stellar_class || 'N/A' }}</li>
          <li><strong>星球类型:</strong> {{ nftData.planet_type || 'N/A' }}</li>
          
          <li class="jph-line"><strong>资源产出:</strong> 💰 {{ formatCurrency(jph) }} JCoin / 小时</li>
          <li class="harvest-line"><strong>收获状态:</strong> 
            <span :class="{ 'ready':  isReadyToHarvest, 'cooldown': ! isReadyToHarvest }">
              {{ harvest_cooldown_str }}
            </span>
          </li>
          
          <li v-if="unlockedTraitNames.length > 0"><strong>已揭示特质:</strong> {{ unlockedTraitNames.join(', ') }}</li>
          <li v-if="nftData.anomalies?.length" class="anomaly"><strong>未探明信号:</strong> {{ nftData.anomalies.length }} 个</li>
      </ul>
      <div v-else class="nft-data-error">[数据加载失败]</div>
      
      <template v-if="context === 'collection' && nft.data">
        
        <div class="action-form harvest-form" v-if="jph > 0">
            <h4>⛏️ 资源收获</h4>
            <p class="help-text">收集该行星累积的 JCoin。冷却时间: {{ (HARVEST_COOLDOWN_SECONDS / 3600).toFixed(1) }} 小时。</p>
            <form @submit.prevent="handleHarvest">
                <button type="submit" :disabled="!isReadyToHarvest">
                  {{ isReadyToHarvest ? `立即收获 (已积累: ${accumulatedJph.toFixed(4)} JCoin)` : harvest_cooldown_str }}
                </button>
            </form>
        </div>
        <div v-if="nftData.anomalies?.length" class="action-form">
            <h4>🛰️ 扫描异常信号</h4>
            <p class="help-text">消耗 {{ SCAN_COST.toFixed(1) }} JCoin 进行深度扫描，可能会有惊人发现。</p>
            <form @submit.prevent="handleScan">
                <div class="form-group">
                    <select v-model="form.scan.selectedAnomaly">
                        <option v-for="anomaly in nftData.anomalies" :key="anomaly" :value="anomaly">
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
                    <input type="text" v-model="form.rename.newName" placeholder="输入新的星球名称" required maxlength="30" />
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
                <label>{{ form.list.listing_type === 'SALE' ? '价格 (JCoin)' : '起拍价 (JCoin)' }}</label>
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
.nft-header, .nft-data, .action-form { padding: 1rem 1.25rem; }
.nft-header { border-bottom: 1px solid #e2e8f0; margin: 0; }
.action-form { border-top: 1px solid #f0f2f5; }
.sell-form { background: #f7fafc; }
.harvest-form { background: #f0fff4; } /* 收获表单用绿色背景 */
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

/* --- V3 产出样式 --- */
.jph-line strong { color: #2f855a; }
.harvest-line span { font-weight: 600; }
.harvest-line span.ready { color: #2f855a; }
.harvest-line span.cooldown { color: #4a5568; }

/* --- Summary 内部样式 (V3 修改) --- */
.summary-wrapper {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: nowrap; /* 防止换行 */
    overflow: hidden;
}
.nft-type-tag {
    font-size: 0.75rem;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-weight: 600;
    color: #2d3748;
    background-color: #e2e8f0;
    flex-shrink: 0;
}
.nft-title {
    font-size: 1.0rem;
    font-weight: 600;
    color: #2d3748;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    flex-shrink: 1; /* 标题可以被压缩 */
}
.nft-status.status-rarity {
    font-size: 0.85rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    flex-shrink: 0;
    color: #975a16;
    background-color: #feebc8;
}
.anomaly-tag {
    font-size: 0.85rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    flex-shrink: 0;
    color: #dd6b20;
    background-color: #fffaf0;
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
</style>