import { createHash, randomBytes, createCipheriv, createDecipheriv } from 'crypto';
import { prisma } from './prisma';

const JWT_SECRET = process.env.JWT_SECRET || 'sota-dev-secret-change-in-production';
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || '0123456789abcdef0123456789abcdef'; // 32 bytes for AES-256

// ═══════════════════════════════════════════════════════════
//  API Key Generation & Validation
// ═══════════════════════════════════════════════════════════

export interface GeneratedApiKey {
  keyId: string;      // Public identifier: "ak_xxxx"
  fullKey: string;    // Full key to show user once: "ak_xxxx.secret_part"
  keyHash: string;    // SHA-256 hash for storage
}

/**
 * Generate a new API key for an agent
 */
export function generateApiKey(): GeneratedApiKey {
  const keyId = `ak_${randomBytes(8).toString('hex')}`;
  const secret = randomBytes(24).toString('hex');
  const fullKey = `${keyId}.${secret}`;
  const keyHash = createHash('sha256').update(fullKey).digest('hex');
  
  return { keyId, fullKey, keyHash };
}

/**
 * Validate an API key and return the associated agent
 */
export async function validateApiKey(fullKey: string) {
  if (!fullKey || !fullKey.includes('.')) {
    return null;
  }
  
  const keyHash = createHash('sha256').update(fullKey).digest('hex');
  
  const apiKey = await prisma.agentApiKey.findFirst({
    where: {
      keyHash,
      isActive: true,
      OR: [
        { expiresAt: null },
        { expiresAt: { gt: new Date() } }
      ]
    },
    include: {
      agent: {
        include: {
          owner: true
        }
      }
    }
  });
  
  if (!apiKey) {
    return null;
  }
  
  // Update last used timestamp
  await prisma.agentApiKey.update({
    where: { id: apiKey.id },
    data: { lastUsedAt: new Date() }
  });
  
  return {
    apiKey,
    agent: apiKey.agent,
    owner: apiKey.agent.owner,
    permissions: apiKey.permissions
  };
}

// ═══════════════════════════════════════════════════════════
//  Encryption for storing third-party API keys
// ═══════════════════════════════════════════════════════════

/**
 * Encrypt a string (for storing developer's external API keys)
 */
export function encryptApiKey(plainText: string): string {
  const iv = randomBytes(16);
  const cipher = createCipheriv('aes-256-cbc', Buffer.from(ENCRYPTION_KEY, 'utf-8'), iv);
  let encrypted = cipher.update(plainText, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  return `${iv.toString('hex')}:${encrypted}`;
}

/**
 * Decrypt a string
 */
export function decryptApiKey(encrypted: string): string {
  const [ivHex, encryptedText] = encrypted.split(':');
  const iv = Buffer.from(ivHex, 'hex');
  const decipher = createDecipheriv('aes-256-cbc', Buffer.from(ENCRYPTION_KEY, 'utf-8'), iv);
  let decrypted = decipher.update(encryptedText, 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  return decrypted;
}

// ═══════════════════════════════════════════════════════════
//  Session Management (Simple JWT-like tokens)
// ═══════════════════════════════════════════════════════════

export interface SessionPayload {
  userId: number;
  walletAddress?: string;
  exp: number;
}

/**
 * Create a session token
 */
export function createSessionToken(payload: Omit<SessionPayload, 'exp'>): string {
  const exp = Date.now() + 7 * 24 * 60 * 60 * 1000; // 7 days
  const data = JSON.stringify({ ...payload, exp });
  const signature = createHash('sha256').update(`${data}${JWT_SECRET}`).digest('hex');
  return Buffer.from(`${data}.${signature}`).toString('base64');
}

/**
 * Verify and decode a session token
 */
export function verifySessionToken(token: string): SessionPayload | null {
  try {
    const decoded = Buffer.from(token, 'base64').toString('utf-8');
    const [data, signature] = decoded.split(/\.(?=[^.]+$)/); // Split on last dot
    
    const expectedSignature = createHash('sha256').update(`${data}${JWT_SECRET}`).digest('hex');
    if (signature !== expectedSignature) {
      return null;
    }
    
    const payload = JSON.parse(data) as SessionPayload;
    if (payload.exp < Date.now()) {
      return null;
    }
    
    return payload;
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════
//  Request Authentication Helpers
// ═══════════════════════════════════════════════════════════

/**
 * Get current user from request headers
 */
export async function getCurrentUser(request: Request) {
  const authHeader = request.headers.get('Authorization');
  
  if (!authHeader) {
    return null;
  }
  
  // Check for Bearer token (session)
  if (authHeader.startsWith('Bearer ')) {
    const token = authHeader.slice(7);
    const payload = verifySessionToken(token);
    
    if (!payload) {
      return null;
    }
    
    const user = await prisma.user.findUnique({
      where: { id: payload.userId }
    });
    
    return user;
  }
  
  // Check for API key
  if (authHeader.startsWith('ApiKey ')) {
    const key = authHeader.slice(7);
    const result = await validateApiKey(key);
    return result?.owner || null;
  }
  
  return null;
}

/**
 * Require authentication - throws if not authenticated
 */
export async function requireAuth(request: Request) {
  const user = await getCurrentUser(request);
  
  if (!user) {
    throw new Error('Unauthorized');
  }
  
  return user;
}

// ═══════════════════════════════════════════════════════════
//  Wallet Signature Verification (for wallet-based auth)
// ═══════════════════════════════════════════════════════════

/**
 * Generate a nonce for wallet signature
 */
export function generateNonce(): string {
  return `Sign this message to authenticate with SOTA:\n\nNonce: ${randomBytes(16).toString('hex')}\nTimestamp: ${Date.now()}`;
}

/**
 * Hash a password
 */
export function hashPassword(password: string): string {
  return createHash('sha256').update(`${password}${JWT_SECRET}`).digest('hex');
}

/**
 * Verify a password
 */
export function verifyPassword(password: string, hash: string): boolean {
  return hashPassword(password) === hash;
}
