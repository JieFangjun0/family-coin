import { markRaw } from 'vue'

// 导入所有渲染器组件
import SecretWishRenderer from './renderers/SecretWishRenderer.vue'
import PlanetRenderer from './renderers/PlanetRenderer.vue'
import DefaultRenderer from './renderers/DefaultRenderer.vue'

// 使用 markRaw 包装组件，这是一个性能优化，
// 告诉 Vue 这些组件不需要被转化为响应式对象。
export const nftRendererRegistry = {
  SECRET_WISH: markRaw(SecretWishRenderer),
  PLANET: markRaw(PlanetRenderer),
  // 当你添加新的NFT时 (e.g. BIO_DNA)，只需在这里添加一行
  // BIO_DNA: markRaw(BioDnaRenderer),
};

export const defaultRenderer = markRaw(DefaultRenderer);