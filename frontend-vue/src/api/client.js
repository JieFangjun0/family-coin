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

export default apiClient;