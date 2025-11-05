import { markRaw } from 'vue'

// 导入默认组件 (Component) 和具名导出 (getSearchableText)
import SecretWishRenderer, { getSearchableText as getSecretWishSearchText } from './renderers/SecretWishRenderer.vue'
import PlanetRenderer, { getSearchableText as getPlanetSearchText } from './renderers/PlanetRenderer.vue'
import BioDnaRenderer, { getSearchableText as getBioDnaSearchText } from './renderers/BioDnaRenderer.vue'
import DefaultRenderer, { getSearchableText as getDefaultSearchText } from './renderers/DefaultRenderer.vue'

/**
 * 默认导出 (DefaultRenderer)
 */
export const defaultRenderer = {
    component: markRaw(DefaultRenderer),
    getSearchableText: getDefaultSearchText
}

/**
 * NFT 渲染器和搜索逻辑的注册表
 * 这满足了将翻译逻辑保留在各自 .vue 文件中的约束
 */
export const nftRendererRegistry = {
  "SECRET_WISH": {
      component: markRaw(SecretWishRenderer),
      getSearchableText: getSecretWishSearchText
  },
  "PLANET": {
      component: markRaw(PlanetRenderer),
      getSearchableText: getPlanetSearchText
  },
  "BIO_DNA": {
      component: markRaw(BioDnaRenderer),
      getSearchableText: getBioDnaSearchText
  },
  // (你未来添加的任何新类型都将遵循此模式)
};