import axios from 'axios'

let triggerLogout;

/**
 * 设置一个全局的登出处理器。
 * @param {Function} handler - 当触发401时调用的函数
 */
export function setLogoutHandler(handler) {
  triggerLogout = handler;
}

const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Axios 响应拦截器
apiClient.interceptors.response.use(
  (response) => response, // 对成功的响应直接放行
  (error) => {
    // 只在 401 Unauthorized 时触发自动登出
    if (error.response && error.response.status === 401) {
      if (triggerLogout) {
        console.warn('Authentication error (401) detected. Triggering auto-logout.');
        triggerLogout();
      }
    }
    // 无论如何，都将错误继续向下传递
    return Promise.reject(error);
  }
);

/**
 * 统一的 API 请求函数。
 * @param {string} method - 'GET', 'POST', 'PUT', 'DELETE'
 * @param {string} endpoint - API 路径 (e.g., '/login')
 * @param {object} [options] - 包含 payload, headers, params 的对象
 * @returns {Promise<[object, string|null]>} - 返回 [data, error] 数组
 */
export async function apiCall(method, endpoint, { payload = null, headers = null, params = null } = {}) {
  try {
    const config = { method, url: endpoint, data: payload, headers, params };
    const response = await apiClient(config);
    return [response.data, null];
  } catch (error) {
    if (error.response) {
      // 后端返回了具体的错误信息
      const errorMessage = error.response.data?.detail || `请求错误，状态码：${error.response.status}`;
      return [null, errorMessage];
    } else if (error.request) {
      // 请求已发出，但没有收到响应
      return [null, '无法连接到服务器，请检查你的网络或联系管理员。'];
    } else {
      // 设置请求时触发了错误
      return [null, `请求失败: ${error.message}`];
    }
  }
}

// 默认导出 axios 实例，以便在其他地方需要时直接使用
export default apiClient;

