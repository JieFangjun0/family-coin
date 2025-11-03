import nacl from 'tweetnacl';

/**
 * Encodes a string into a Uint8Array using UTF-8.
 * A necessary replacement for the problematic noble library utils.
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
 * Parses a PEM-formatted Ed25519 private key.
 * @param {string} pem The PEM string.
 * @returns {Uint8Array} The raw 64-byte key pair (seed + public key).
 */
function privateKeyFromPem(pem) {
  const pemContents = pem
    .replace('-----BEGIN PRIVATE KEY-----', '')
    .replace('-----END PRIVATE KEY-----', '')
    .replace(/\s/g, '');

  const buffer = base64ToBytes(pemContents);
  
  // For Ed25519 in PKCS8 format, the raw private key (seed) is the last 32 bytes.
  // tweetnacl expects a 64-byte keypair, which can be generated from the 32-byte seed.
  const seed = buffer.slice(-32);
  return nacl.sign.keyPair.fromSeed(seed).secretKey;
}

/**
 * Creates a signed payload for a given message object.
 * @param {string} privateKeyPem The user's private key in PEM format.
 * @param {object} message The message object to sign.
 * @returns {{message_json: string, signature: string}|null}
 */
export function createSignedPayload(privateKeyPem, message) {
  try {
    const secretKey = privateKeyFromPem(privateKeyPem);

    // IMPORTANT: Create a canonical JSON string, same as the Python backend.
    const messageJson = JSON.stringify(message, Object.keys(message).sort());
    const messageBytes = utf8ToBytes(messageJson);

    // Sign the message bytes
    const signatureBytes = nacl.sign.detached(messageBytes, secretKey);

    // Encode signature to Base64
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