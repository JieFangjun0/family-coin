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

/**
 * 从 PEM 格式的私钥中解析出 32 字节的种子密钥 (seed)。
 * 这是连接 Python 后端和 tweetnacl 前端的关键桥梁。
 * @param {string} pem The PEM string.
 * @returns {Uint8Array} The raw 32-byte seed.
 */
function getSeedFromPem(pem) {
  const pemContents = pem
    .replace('-----BEGIN PRIVATE KEY-----', '')
    .replace('-----END PRIVATE KEY-----', '')
    .replace(/\s/g, '');

  const buffer = base64ToBytes(pemContents);
  // 在 Ed25519 的 PKCS#8 格式中，原始的种子密钥就是最后 32 个字节。
  const seed = buffer.slice(-32);

  if (seed.length !== 32) {
    throw new Error('解析 PEM 失败：种子密钥长度不是 32 字节。');
  }
  
  return seed;
}

/**
 * 使用 tweetnacl 创建一个已签名的载荷。
 * @param {string} privateKeyPem 用户的 PEM 格式私钥。
 * @param {object} message 需要签名的消息对象。
 * @returns {{message_json: string, signature: string}|null}
 */
export function createSignedPayload(privateKeyPem, message) {
  // 注意：这个函数不再是 async 的，因为 tweetnacl 是同步库
  try {
    // 1. 从 PEM 中获取 32 字节的种子
    const seed = getSeedFromPem(privateKeyPem);

    // 2. 从种子生成 tweetnacl 需要的完整密钥对
    const keyPair = nacl.sign.keyPair.fromSeed(seed);
    const secretKey = keyPair.secretKey; // 这是签名所需的 64 字节密钥

    // 3. 规范化消息（与之前完全相同）
    const sortedMessage = Object.keys(message)
      .sort()
      .reduce((obj, key) => {
        obj[key] = message[key];
        return obj;
      }, {});
    const messageJson = JSON.stringify(sortedMessage);
    const messageBytes = utf8ToBytes(messageJson);

    // 4. 使用分离式签名函数进行签名
    const signatureBytes = nacl.sign.detached(messageBytes, secretKey);

    // 5. 将签名编码为 Base64
    const signatureBase64 = bytesToBase64(signatureBytes);
      // --- DEBUGGING STEP: 打印前端生成的所有用于签名的数据 ---
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