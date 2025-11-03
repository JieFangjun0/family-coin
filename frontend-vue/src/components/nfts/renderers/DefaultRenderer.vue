<!-- 架构已统一：Vue前端现在完全遵循了你最初设计的、基于context的解耦渲染模式。ShopView.vue 只负责展示商品框架（价格、卖家），而商品具体内容的展示则完全交由各个独立的NFT渲染器组件负责。
可维护性增强：未来添加新的NFT类型，你只需要创建一个新的渲染器组件，在其中定义好 collection 和 market 两种上下文的显示方式，然后在 renderer-registry.js 中注册即可，ShopView.vue 无需任何改动。 -->
<script setup>
defineProps({
  nft: {
    type: Object,
    required: true
  }
})
// 这个备用组件不提供上架功能
</script>

<template>
    <div class="nft-header">
        <span class="nft-type-unknown">{{ nft.nft_type }}</span>
        <h3 class="nft-name">未知类型的 NFT</h3>
    </div>
    <div class="nft-data">
        <p>没有找到该类型的专属渲染器。以下是它的原始数据：</p>
        <pre>{{ JSON.stringify(nft.data, null, 2) }}</pre>
    </div>
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
</style>