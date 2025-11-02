import axios from 'axios'
// 我们需要从 auth store 中导入一个函数来触发登出
// 但为了避免循环依赖，我们不直接导入 store 实例
let triggerLogout;
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
    // 检查是否是需要自动登出的特定错误
    if (error.response && [401, 403, 404].includes(error.response.status)) {
      // 检查错误信息是否与用户认证有关
      const detail = error.response.data?.detail?.toLowerCase() || '';
      const isAuthError = detail.includes('签名无效') || 
                          detail.includes('未找到用户') || 
                          detail.includes('not found') ||
                          detail.includes('unauthorized');

      if (isAuthError && triggerLogout) {
        console.warn('Authentication error detected. Triggering auto-logout.');
        triggerLogout();
      }
    }
    // 无论如何，都将错误继续向下传递
    return Promise.reject(error);
  }
);


export async function apiCall(method, endpoint, { payload = null, headers = null, params = null } = {}) {
  try {
    const config = { method, url: endpoint, data: payload, headers, params };
    const response = await apiClient(config);
    return [response.data, null];
  } catch (error) {
    if (error.response) {
      const errorMessage = error.response.data?.detail || `请求错误，状态码：${error.response.status}`;
      return [null, errorMessage];
    } else if (error.request) {
      return [null, '无法连接到服务器，请检查你的网络或联系管理员。'];
    } else {
      return [null, `请求失败: ${error.message}`];
    }
  }
}

export default apiClient;