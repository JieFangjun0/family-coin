// /frontend-vue/src/utils/formatters.js

/**
 * @fileoverview Utility functions for formatting data.
 */

/**
 * Formats a Unix timestamp into a human-readable date and time string.
 * @param {number} timestamp - The Unix timestamp in seconds.
 * @returns {string} - The formatted date string (e.g., "2025-11-02 14:30:15"), or 'N/A' if invalid.
 */
export function formatTimestamp(timestamp) {
  // *** 核心修改：使用更健壮的检查 ***
  // 旧检查 (if (!timestamp || ...)) 会错误地将 0 视为无效
  if (typeof timestamp !== 'number' || isNaN(timestamp)) {
    return 'N/A';
  }
  // JS Date constructor expects milliseconds, so we multiply by 1000.
  const date = new Date(timestamp * 1000);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false, // Use 24-hour format
  }).replace(/\//g, '-');
}

/**
 * Formats a number into a currency string with commas.
 * @param {number} value - The number to format.
 * @returns {string} - The formatted currency string (e.g., "1,234.56").
 */
export function formatCurrency(value) {
  if (typeof value !== 'number') {
    return '0.00';
  }
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}