// frontend-vue/src/utils/crypto.js

import nacl from 'tweetnacl';

function utf8ToBytes(str) {
  return new TextEncoder().encode(str);
}

function base64ToBytes(base64) {
  const binString = atob(base64);
  return Uint8Array.from(binString, (m) => m.codePointAt(0));
}

function bytesToBase64(bytes) {
  const binString = String.fromCodePoint(...bytes);
  return btoa(binString);
}

function getSeedFromPem(pem) {
  // ... (此函数保持不变)
  const pemContents = pem
    .replace('-----BEGIN PRIVATE KEY-----', '')
    .replace('-----END PRIVATE KEY-----', '')
    .replace(/\s/g, '');

  const buffer = base64ToBytes(pemContents);
  const seed = buffer.slice(-32);

  if (seed.length !== 32) {
    throw new Error('解析 PEM 失败：种子密钥长度不是 32 字节。');
  }
  
  return seed;
}

// +++ 新增：一个能递归排序对象键的函数 +++
const getCanonicalObject = (obj) => {
  if (obj === null || typeof obj !== 'object' || Array.isArray(obj)) {
    return obj;
  }

  const sortedObj = {};
  Object.keys(obj)
    .sort()
    .forEach(key => {
      sortedObj[key] = getCanonicalObject(obj[key]);
    });

  return sortedObj;
};


export function createSignedPayload(privateKeyPem, message) {
  try {
    const seed = getSeedFromPem(privateKeyPem);
    const keyPair = nacl.sign.keyPair.fromSeed(seed);
    const secretKey = keyPair.secretKey;

    // +++ 核心修改：使用新的函数进行深度排序 +++
    const canonicalMessage = getCanonicalObject(message);
    const messageJson = JSON.stringify(canonicalMessage);
    const messageBytes = utf8ToBytes(messageJson);

    const signatureBytes = nacl.sign.detached(messageBytes, secretKey);
    const signatureBase64 = bytesToBase64(signatureBytes);
    
    console.log('--- Frontend Crypto Debug ---');
    console.log('1. Canonical Message JSON for Signing:', messageJson);
    console.log('2. Generated Signature (Base64):', signatureBase64);
    console.log('---------------------------');
    
    return {
      message_json: messageJson,
      signature: signatureBase64,
    };
  } catch (error) {
    console.error('使用 tweetnacl 创建签名载荷失败:', error);
    return null;
  }
}