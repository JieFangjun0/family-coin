import * as ed25519 from '@noble/ed25519';
// --- 最终修正：从正确的子模块 '@noble/hashes/sha2' 导入 sha512 ---
import { sha512 } from '@noble/hashes/sha2';

// 将 sha512 哈希函数 "注入" 到 ed25519 库中
ed25519.utils.sha512 = sha512;

/**
 * Encodes a string into a Uint8Array using UTF-8.
 * @param {string} str The string to encode.
 * @returns {Uint8Array}
 */
function utf8ToBytes(str) {
  return new TextEncoder().encode(str);
}

/**
 * Decodes a Base64 string into a Uint8Array.
 * @param {string} base64 The Base64 string.
 * @returns {Uint8Array}
 */
function base64ToBytes(base64) {
  const binString = atob(base64);
  return Uint8Array.from(binString, (m) => m.codePointAt(0));
}

/**
 * Encodes a Uint8Array into a Base64 string.
 * @param {Uint8Array} bytes The byte array.
 * @returns {string}
 */
function bytesToBase64(bytes) {
  const binString = String.fromCodePoint(...bytes);
  return btoa(binString);
}

/**
 * Parses a PEM-formatted Ed25519 private key (PKCS#8).
 * @param {string} pem The PEM string.
 * @returns {Uint8Array} The raw 32-byte private key (seed).
 */
function privateKeyFromPem(pem) {
  const pemContents = pem
    .replace('-----BEGIN PRIVATE KEY-----', '')
    .replace('-----END PRIVATE KEY-----', '')
    .replace(/\s/g, '');

  const buffer = base64ToBytes(pemContents);
  const privateKeyBytes = buffer.slice(-32);

  if (privateKeyBytes.length !== 32) {
    throw new Error('Failed to parse PEM: private key is not 32 bytes long.');
  }
  
  return privateKeyBytes;
}

/**
 * Creates a signed payload for a given message object.
 * @param {string} privateKeyPem The user's private key in PEM format.
 * @param {object} message The message object to sign.
 * @returns {Promise<{message_json: string, signature: string}|null>}
 */
export async function createSignedPayload(privateKeyPem, message) {
  try {
    const privateKey = privateKeyFromPem(privateKeyPem);

    const sortedMessage = Object.keys(message)
      .sort()
      .reduce((obj, key) => {
        obj[key] = message[key];
        return obj;
      }, {});
    const messageJson = JSON.stringify(sortedMessage);
    const messageBytes = utf8ToBytes(messageJson);

    const signatureBytes = await ed25519.sign(messageBytes, privateKey);

    const signatureBase64 = bytesToBase64(signatureBytes);

    return {
      message_json: messageJson,
      signature: signatureBase64,
    };
  } catch (error) {
    console.error('Failed to create signed payload:', error);
    return null;
  }
}