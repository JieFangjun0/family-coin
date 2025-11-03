// family-coin-vue-refactor/frontend-vue/src/api/index.js

import apiClient from './client'

/**
 * 统一的 API 请求函数
 * @param {string} method - HTTP 方法 (e.g., 'GET', 'POST')
 * @param {string} url - 请求的 API 路径 (e.g., '/status')
 * @param {object} [options] - 可选参数
 * @param {object} [options.payload] - 请求体 (用于 POST, PUT 等)
 * @param {object} [options.params] - URL 查询参数 (用于 GET)
 * @param {object} [options.headers] - HTTP 请求头
 * @returns {Promise<[any, string|null]>} - 返回一个元组 [data, error]
 */
export async function apiCall(method, url, { payload = null, params = null, headers = null } = {}) {
  try {
    const config = {
      method,
      url,
      data: payload,
      params,
      headers, // <-- 核心修正：将 headers 添加到 config 对象中
    }
    const response = await apiClient(config)
    // 请求成功，返回 [数据, null]
    return [response.data, null]
  } catch (error) {
    // 从 Axios 错误中提取后端返回的具体错误信息
    const errorMessage = error.response?.data?.detail || error.message || 'An unknown network error occurred.'
    // 请求失败，返回 [null, 错误信息]
    return [null, errorMessage]
  }
}