/**
 * Firestore Database Layer
 * 
 * Drop-in replacement for Prisma queries, backed by Firebase Firestore.
 * Mirrors every model from prisma/schema.prisma:
 *   User, Agent, Order, CallSummary, MarketplaceJob, UserProfile,
 *   AgentDataRequest, AgentJobUpdate, AgentApiKey, Session
 */

import * as admin from 'firebase-admin';
import { getAdmin } from './firebase-admin';

let _db: admin.firestore.Firestore | null = null;
function getDb() {
  if (!_db) {
    _db = admin.firestore(getAdmin());
  }
  return _db;
}

// Proxy so all existing code using `db.collection(...)` etc. works unchanged
const db = new Proxy({} as admin.firestore.Firestore, {
  get(_, prop) {
    return (getDb() as any)[prop];
  },
});

// ═══════════════════════════════════════════════════════════
//  Collection references (lazy — only resolved on first access)
// ═══════════════════════════════════════════════════════════

const collectionNames = {
  users: 'users',
  agents: 'agents',
  orders: 'orders',
  callSummaries: 'callSummaries',
  marketplaceJobs: 'marketplaceJobs',
  userProfiles: 'userProfiles',
  agentDataRequests: 'agentDataRequests',
  agentJobUpdates: 'agentJobUpdates',
  agentApiKeys: 'agentApiKeys',
  sessions: 'sessions',
  counters: 'counters',
} as const;

type CollectionRefs = { [K in keyof typeof collectionNames]: admin.firestore.CollectionReference };

export const collections = new Proxy({} as CollectionRefs, {
  get(target, prop: string) {
    if (prop in collectionNames) {
      return db.collection(collectionNames[prop as keyof typeof collectionNames]);
    }
    return undefined;
  },
});

// ═══════════════════════════════════════════════════════════
//  Auto-increment IDs (mimics Prisma @id @default(autoincrement()))
// ═══════════════════════════════════════════════════════════

async function nextId(counterName: string): Promise<number> {
  const ref = collections.counters.doc(counterName);
  const result = await db.runTransaction(async (tx) => {
    const snap = await tx.get(ref);
    const current = snap.exists ? (snap.data()!.value as number) : 0;
    const next = current + 1;
    tx.set(ref, { value: next });
    return next;
  });
  return result;
}

// ═══════════════════════════════════════════════════════════
//  Type definitions matching Prisma models
// ═══════════════════════════════════════════════════════════

export interface DbUser {
  id: number;
  firebaseUid: string | null;
  email: string;
  passwordHash: string;
  name: string | null;
  walletAddress: string | null;
  role: string;
  createdAt: Date;
}

export interface DbAgent {
  id: number;
  title: string;
  description: string;
  category: string | null;
  priceUsd: number;
  status: string;
  tags: string | null;
  network: string | null;
  image: string | null;
  walletAddress: string | null;
  ownerId: number;
  createdAt: Date;
  updatedAt: Date;
  apiEndpoint: string | null;
  apiKey: string | null;
  apiKeyHash: string | null;
  capabilities: string | null;
  webhookUrl: string | null;
  onchainAddress: string | null;
  isVerified: boolean;
  documentation: string | null;
  minFeeUsdc: number;
  maxConcurrent: number;
  bidAggressiveness: number;
  totalRequests: number;
  successfulRequests: number;
  reputation: number;
  icon: string | null;
}

export interface DbOrder {
  id: number;
  agentId: number;
  buyerId: number | null;
  txHash: string;
  amountEth: number;
  network: string;
  walletAddress: string;
  createdAt: Date;
}

export interface DbCallSummary {
  id: number;
  conversationId: string | null;
  callSid: string | null;
  status: string | null;
  summary: string | null;
  toNumber: string | null;
  jobId: string | null;
  neofsUri: string | null;
  payload: Record<string, unknown> | null;
  createdAt: Date;
}

export interface DbMarketplaceJob {
  id: number;
  jobId: string;
  description: string;
  tags: string[];
  budgetUsdc: number;
  status: string;
  poster: string | null;
  winner: string | null;
  winnerPrice: number | null;
  metadata: Record<string, unknown> | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface DbUserProfile {
  id: number;
  userId: string;
  fullName: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  skills: string | null;
  experienceLevel: string | null;
  githubUrl: string | null;
  linkedinUrl: string | null;
  portfolioUrl: string | null;
  bio: string | null;
  preferences: Record<string, unknown> | null;
  extra: Record<string, unknown> | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface DbAgentDataRequest {
  id: number;
  requestId: string;
  jobId: string;
  agent: string;
  dataType: string;
  question: string;
  fields: string[];
  context: string | null;
  status: string;
  answerData: Record<string, unknown> | null;
  answerMsg: string | null;
  createdAt: Date;
  answeredAt: Date | null;
}

export interface DbAgentJobUpdate {
  id: number;
  jobId: string;
  agent: string;
  status: string;
  message: string;
  data: Record<string, unknown> | null;
  createdAt: Date;
}

export interface DbAgentApiKey {
  id: number;
  keyId: string;
  keyHash: string;
  agentId: number;
  name: string;
  permissions: string[];
  lastUsedAt: Date | null;
  expiresAt: Date | null;
  isActive: boolean;
  createdAt: Date;
}

export interface DbSession {
  id: number;
  sessionId: string;
  userId: number;
  walletAddress: string | null;
  expiresAt: Date;
  createdAt: Date;
}

// ═══════════════════════════════════════════════════════════
//  Helper: convert Firestore Timestamps → JS Dates
// ═══════════════════════════════════════════════════════════

function toDate(v: unknown): Date {
  if (v instanceof admin.firestore.Timestamp) return v.toDate();
  if (v instanceof Date) return v;
  if (typeof v === 'string') return new Date(v);
  return new Date();
}

function docToRecord<T>(snap: admin.firestore.DocumentSnapshot): T {
  const data = snap.data()!;
  // Convert all Timestamp fields to Date
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    if (v instanceof admin.firestore.Timestamp) {
      result[k] = v.toDate();
    } else {
      result[k] = v;
    }
  }
  return result as T;
}

// ═══════════════════════════════════════════════════════════
//  USER operations
// ═══════════════════════════════════════════════════════════

export const userDb = {
  async findUnique(where: { id?: number; email?: string; firebaseUid?: string }): Promise<DbUser | null> {
    let snap: admin.firestore.QuerySnapshot;

    if (where.id !== undefined) {
      snap = await collections.users.where('id', '==', where.id).limit(1).get();
    } else if (where.email) {
      snap = await collections.users.where('email', '==', where.email).limit(1).get();
    } else if (where.firebaseUid) {
      snap = await collections.users.where('firebaseUid', '==', where.firebaseUid).limit(1).get();
    } else {
      return null;
    }

    if (snap.empty) return null;
    return docToRecord<DbUser>(snap.docs[0]);
  },

  async create(data: Omit<DbUser, 'id' | 'createdAt'> & { createdAt?: Date }): Promise<DbUser> {
    const id = await nextId('users');
    const user: DbUser = {
      id,
      firebaseUid: data.firebaseUid ?? null,
      email: data.email,
      passwordHash: data.passwordHash ?? '',
      name: data.name ?? null,
      walletAddress: data.walletAddress ?? null,
      role: data.role ?? 'user',
      createdAt: data.createdAt ?? new Date(),
    };
    await collections.users.doc(String(id)).set(user);
    return user;
  },

  async upsert(
    where: { firebaseUid?: string; email?: string },
    update: Partial<DbUser>,
    create: Omit<DbUser, 'id' | 'createdAt'>,
  ): Promise<DbUser> {
    const existing = await this.findUnique(where);
    if (existing) {
      const ref = collections.users.doc(String(existing.id));
      await ref.update(update);
      return { ...existing, ...update };
    }
    return this.create(create);
  },

  async findMany(opts?: { where?: Partial<DbUser>; orderBy?: string; take?: number }): Promise<DbUser[]> {
    let q: admin.firestore.Query = collections.users;
    if (opts?.orderBy) q = q.orderBy(opts.orderBy);
    if (opts?.take) q = q.limit(opts.take);
    const snap = await q.get();
    return snap.docs.map(d => docToRecord<DbUser>(d));
  },
};

// ═══════════════════════════════════════════════════════════
//  AGENT operations
// ═══════════════════════════════════════════════════════════

export const agentDb = {
  async findUnique(where: { id: number }): Promise<DbAgent | null> {
    const snap = await collections.agents.where('id', '==', where.id).limit(1).get();
    if (snap.empty) return null;
    return docToRecord<DbAgent>(snap.docs[0]);
  },

  async findMany(opts?: {
    where?: Omit<Partial<DbAgent>, 'status'> & { status?: string | { in: string[] } };
    orderBy?: Record<string, 'asc' | 'desc'>;
    select?: Record<string, boolean>;
    include?: Record<string, unknown>;
    take?: number;
  }): Promise<DbAgent[]> {
    let q: admin.firestore.Query = collections.agents;

    if (opts?.where) {
      for (const [key, value] of Object.entries(opts.where)) {
        if (value === undefined) continue;
        if (typeof value === 'object' && value !== null && 'in' in value) {
          q = q.where(key, 'in', (value as { in: unknown[] }).in);
        } else {
          q = q.where(key, '==', value);
        }
      }
    }

    if (opts?.orderBy) {
      for (const [field, dir] of Object.entries(opts.orderBy)) {
        q = q.orderBy(field, dir);
      }
    }

    if (opts?.take) q = q.limit(opts.take);

    const snap = await q.get();
    let agents = snap.docs.map(d => docToRecord<DbAgent>(d));

    // If include.owner requested, hydrate owner relation
    if (opts?.include?.owner) {
      agents = await Promise.all(
        agents.map(async (agent) => {
          const owner = await userDb.findUnique({ id: agent.ownerId });
          return { ...agent, owner } as DbAgent & { owner: DbUser | null };
        })
      );
    }

    return agents;
  },

  async create(data: Partial<DbAgent> & { title: string; description: string; ownerId: number }): Promise<DbAgent> {
    const id = await nextId('agents');
    const now = new Date();
    const agent: DbAgent = {
      id,
      title: data.title,
      description: data.description,
      category: data.category ?? null,
      priceUsd: data.priceUsd ?? 0,
      status: data.status ?? 'active',
      tags: data.tags ?? null,
      network: data.network ?? 'sepolia',
      image: data.image ?? null,
      walletAddress: data.walletAddress ?? null,
      ownerId: data.ownerId,
      createdAt: now,
      updatedAt: now,
      apiEndpoint: data.apiEndpoint ?? null,
      apiKey: data.apiKey ?? null,
      apiKeyHash: data.apiKeyHash ?? null,
      capabilities: data.capabilities ?? null,
      webhookUrl: data.webhookUrl ?? null,
      onchainAddress: data.onchainAddress ?? null,
      isVerified: data.isVerified ?? false,
      documentation: data.documentation ?? null,
      minFeeUsdc: data.minFeeUsdc ?? 0.01,
      maxConcurrent: data.maxConcurrent ?? 5,
      bidAggressiveness: data.bidAggressiveness ?? 0.8,
      totalRequests: data.totalRequests ?? 0,
      successfulRequests: data.successfulRequests ?? 0,
      reputation: data.reputation ?? 5.0,
      icon: data.icon ?? null,
    };
    await collections.agents.doc(String(id)).set(agent);
    return agent;
  },

  async update(where: { id: number }, data: Record<string, unknown>): Promise<DbAgent> {
    const docSnap = await collections.agents.where('id', '==', where.id).limit(1).get();
    if (docSnap.empty) throw new Error(`Agent ${where.id} not found`);
    const ref = docSnap.docs[0].ref;

    // Handle Prisma-style increment
    const updateData: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data)) {
      if (value && typeof value === 'object' && 'increment' in (value as Record<string, unknown>)) {
        updateData[key] = admin.firestore.FieldValue.increment(
          (value as { increment: number }).increment
        );
      } else if (value !== undefined) {
        updateData[key] = value;
      }
    }
    updateData.updatedAt = new Date();

    await ref.update(updateData);
    const updated = await ref.get();
    return docToRecord<DbAgent>(updated);
  },

  async delete(where: { id: number }): Promise<void> {
    const docSnap = await collections.agents.where('id', '==', where.id).limit(1).get();
    if (!docSnap.empty) {
      await docSnap.docs[0].ref.delete();
    }
  },
};

// ═══════════════════════════════════════════════════════════
//  ORDER operations
// ═══════════════════════════════════════════════════════════

export const orderDb = {
  async create(data: Omit<DbOrder, 'id' | 'createdAt'>): Promise<DbOrder> {
    const id = await nextId('orders');
    const order: DbOrder = { id, ...data, createdAt: new Date() };
    await collections.orders.doc(String(id)).set(order);
    return order;
  },

  async findMany(opts?: {
    where?: Partial<DbOrder>;
    orderBy?: Record<string, 'asc' | 'desc'>;
    take?: number;
  }): Promise<DbOrder[]> {
    let q: admin.firestore.Query = collections.orders;
    if (opts?.where) {
      for (const [k, v] of Object.entries(opts.where)) {
        if (v !== undefined) q = q.where(k, '==', v);
      }
    }
    if (opts?.orderBy) {
      for (const [f, d] of Object.entries(opts.orderBy)) q = q.orderBy(f, d);
    }
    if (opts?.take) q = q.limit(opts.take);
    const snap = await q.get();
    return snap.docs.map(d => docToRecord<DbOrder>(d));
  },
};

// ═══════════════════════════════════════════════════════════
//  CALL SUMMARY operations
// ═══════════════════════════════════════════════════════════

export const callSummaryDb = {
  async create(data: Omit<DbCallSummary, 'id' | 'createdAt'>): Promise<DbCallSummary> {
    const id = await nextId('callSummaries');
    const record: DbCallSummary = { id, ...data, createdAt: new Date() };
    await collections.callSummaries.doc(String(id)).set(record);
    return record;
  },

  async findMany(opts?: {
    where?: Partial<DbCallSummary>;
    orderBy?: Record<string, 'asc' | 'desc'>;
    take?: number;
  }): Promise<DbCallSummary[]> {
    let q: admin.firestore.Query = collections.callSummaries;
    if (opts?.where) {
      for (const [k, v] of Object.entries(opts.where)) {
        if (v !== undefined) q = q.where(k, '==', v);
      }
    }
    if (opts?.orderBy) {
      for (const [f, d] of Object.entries(opts.orderBy)) q = q.orderBy(f, d);
    }
    if (opts?.take) q = q.limit(opts.take);
    const snap = await q.get();
    return snap.docs.map(d => docToRecord<DbCallSummary>(d));
  },
};

// ═══════════════════════════════════════════════════════════
//  MARKETPLACE JOB operations
// ═══════════════════════════════════════════════════════════

export const marketplaceJobDb = {
  async findUnique(where: { jobId?: string; id?: number }): Promise<DbMarketplaceJob | null> {
    let snap: admin.firestore.QuerySnapshot;
    if (where.jobId) {
      snap = await collections.marketplaceJobs.where('jobId', '==', where.jobId).limit(1).get();
    } else if (where.id !== undefined) {
      snap = await collections.marketplaceJobs.where('id', '==', where.id).limit(1).get();
    } else {
      return null;
    }
    if (snap.empty) return null;
    return docToRecord<DbMarketplaceJob>(snap.docs[0]);
  },

  async findMany(opts?: {
    where?: Omit<Partial<DbMarketplaceJob>, 'status'> & { status?: string | { in: string[] } };
    orderBy?: Record<string, 'asc' | 'desc'>;
    include?: { updates?: { orderBy?: Record<string, 'asc' | 'desc'>; take?: number }; requests?: boolean };
    take?: number;
  }): Promise<(DbMarketplaceJob & { updates?: DbAgentJobUpdate[]; requests?: DbAgentDataRequest[] })[]> {
    let q: admin.firestore.Query = collections.marketplaceJobs;

    if (opts?.where) {
      for (const [key, value] of Object.entries(opts.where)) {
        if (value === undefined) continue;
        if (typeof value === 'object' && value !== null && 'in' in value) {
          q = q.where(key, 'in', (value as { in: unknown[] }).in);
        } else {
          q = q.where(key, '==', value);
        }
      }
    }

    if (opts?.orderBy) {
      for (const [f, d] of Object.entries(opts.orderBy)) q = q.orderBy(f, d);
    }

    if (opts?.take) q = q.limit(opts.take);

    const snap = await q.get();
    let jobs = snap.docs.map(d => docToRecord<DbMarketplaceJob>(d));

    // Hydrate relations if requested
    if (opts?.include?.updates) {
      jobs = await Promise.all(
        jobs.map(async (job) => {
          let uq: admin.firestore.Query = collections.agentJobUpdates.where('jobId', '==', job.jobId);
          if (opts.include!.updates!.orderBy) {
            for (const [f, d] of Object.entries(opts.include!.updates!.orderBy!)) {
              uq = uq.orderBy(f, d);
            }
          }
          if (opts.include!.updates!.take) uq = uq.limit(opts.include!.updates!.take!);
          const usnap = await uq.get();
          return { ...job, updates: usnap.docs.map(d => docToRecord<DbAgentJobUpdate>(d)) };
        })
      );
    }

    return jobs;
  },

  async create(data: Omit<DbMarketplaceJob, 'id' | 'createdAt' | 'updatedAt'>): Promise<DbMarketplaceJob> {
    const id = await nextId('marketplaceJobs');
    const now = new Date();
    const job: DbMarketplaceJob = { id, ...data, createdAt: now, updatedAt: now };
    await collections.marketplaceJobs.doc(String(id)).set(job);
    return job;
  },

  async update(where: { jobId?: string; id?: number }, data: Partial<DbMarketplaceJob>): Promise<DbMarketplaceJob> {
    let snap: admin.firestore.QuerySnapshot;
    if (where.jobId) {
      snap = await collections.marketplaceJobs.where('jobId', '==', where.jobId).limit(1).get();
    } else {
      snap = await collections.marketplaceJobs.where('id', '==', where.id).limit(1).get();
    }
    if (snap.empty) throw new Error('MarketplaceJob not found');
    const ref = snap.docs[0].ref;
    const updateData = { ...data, updatedAt: new Date() };
    await ref.update(updateData);
    const updated = await ref.get();
    return docToRecord<DbMarketplaceJob>(updated);
  },
};

// ═══════════════════════════════════════════════════════════
//  USER PROFILE operations
// ═══════════════════════════════════════════════════════════

export const userProfileDb = {
  async findUnique(where: { userId: string }): Promise<DbUserProfile | null> {
    const snap = await collections.userProfiles.where('userId', '==', where.userId).limit(1).get();
    if (snap.empty) return null;
    return docToRecord<DbUserProfile>(snap.docs[0]);
  },

  async upsert(
    where: { userId: string },
    update: Partial<DbUserProfile>,
    create: Omit<DbUserProfile, 'id' | 'createdAt' | 'updatedAt'>,
  ): Promise<DbUserProfile> {
    const existing = await this.findUnique(where);
    const now = new Date();
    if (existing) {
      const ref = collections.userProfiles.doc(String(existing.id));
      await ref.update({ ...update, updatedAt: now });
      return { ...existing, ...update, updatedAt: now };
    }
    const id = await nextId('userProfiles');
    const profile: DbUserProfile = { id, ...create, createdAt: now, updatedAt: now };
    await collections.userProfiles.doc(String(id)).set(profile);
    return profile;
  },

  async findMany(): Promise<DbUserProfile[]> {
    const snap = await collections.userProfiles.get();
    return snap.docs.map(d => docToRecord<DbUserProfile>(d));
  },
};

// ═══════════════════════════════════════════════════════════
//  AGENT DATA REQUEST operations
// ═══════════════════════════════════════════════════════════

export const agentDataRequestDb = {
  async findUnique(where: { requestId: string }): Promise<DbAgentDataRequest | null> {
    const snap = await collections.agentDataRequests.where('requestId', '==', where.requestId).limit(1).get();
    if (snap.empty) return null;
    return docToRecord<DbAgentDataRequest>(snap.docs[0]);
  },

  async findMany(opts?: {
    where?: Partial<DbAgentDataRequest>;
    orderBy?: Record<string, 'asc' | 'desc'>;
    take?: number;
  }): Promise<DbAgentDataRequest[]> {
    let q: admin.firestore.Query = collections.agentDataRequests;
    if (opts?.where) {
      for (const [k, v] of Object.entries(opts.where)) {
        if (v !== undefined) q = q.where(k, '==', v);
      }
    }
    if (opts?.orderBy) {
      for (const [f, d] of Object.entries(opts.orderBy)) q = q.orderBy(f, d);
    }
    if (opts?.take) q = q.limit(opts.take);
    const snap = await q.get();
    return snap.docs.map(d => docToRecord<DbAgentDataRequest>(d));
  },

  async create(data: Omit<DbAgentDataRequest, 'id' | 'createdAt'>): Promise<DbAgentDataRequest> {
    const id = await nextId('agentDataRequests');
    const record: DbAgentDataRequest = { id, ...data, createdAt: new Date() };
    await collections.agentDataRequests.doc(String(id)).set(record);
    return record;
  },

  async update(where: { requestId: string }, data: Partial<DbAgentDataRequest>): Promise<DbAgentDataRequest> {
    const snap = await collections.agentDataRequests.where('requestId', '==', where.requestId).limit(1).get();
    if (snap.empty) throw new Error('AgentDataRequest not found');
    const ref = snap.docs[0].ref;
    await ref.update(data);
    const updated = await ref.get();
    return docToRecord<DbAgentDataRequest>(updated);
  },
};

// ═══════════════════════════════════════════════════════════
//  AGENT JOB UPDATE operations
// ═══════════════════════════════════════════════════════════

export const agentJobUpdateDb = {
  async create(data: Omit<DbAgentJobUpdate, 'id' | 'createdAt'>): Promise<DbAgentJobUpdate> {
    const id = await nextId('agentJobUpdates');
    const record: DbAgentJobUpdate = { id, ...data, createdAt: new Date() };
    await collections.agentJobUpdates.doc(String(id)).set(record);
    return record;
  },

  async findMany(opts?: {
    where?: Partial<DbAgentJobUpdate>;
    orderBy?: Record<string, 'asc' | 'desc'>;
    take?: number;
  }): Promise<DbAgentJobUpdate[]> {
    let q: admin.firestore.Query = collections.agentJobUpdates;
    if (opts?.where) {
      for (const [k, v] of Object.entries(opts.where)) {
        if (v !== undefined) q = q.where(k, '==', v);
      }
    }
    if (opts?.orderBy) {
      for (const [f, d] of Object.entries(opts.orderBy)) q = q.orderBy(f, d);
    }
    if (opts?.take) q = q.limit(opts.take);
    const snap = await q.get();
    return snap.docs.map(d => docToRecord<DbAgentJobUpdate>(d));
  },
};

// ═══════════════════════════════════════════════════════════
//  AGENT API KEY operations
// ═══════════════════════════════════════════════════════════

export const agentApiKeyDb = {
  async findFirst(opts: {
    where: Partial<DbAgentApiKey> & {
      OR?: Array<Record<string, unknown>>;
    };
    include?: { agent?: { include?: { owner?: boolean } } | boolean };
  }): Promise<(DbAgentApiKey & { agent?: DbAgent & { owner?: DbUser | null } }) | null> {
    // Primary filter: keyHash + isActive
    let q: admin.firestore.Query = collections.agentApiKeys;
    
    const { OR, ...simpleWhere } = opts.where;
    for (const [k, v] of Object.entries(simpleWhere)) {
      if (v !== undefined) q = q.where(k, '==', v);
    }

    const snap = await q.limit(10).get();
    if (snap.empty) return null;

    // Apply OR filter in memory (Firestore doesn't support arbitrary OR + other where)
    let docs = snap.docs.map(d => docToRecord<DbAgentApiKey>(d));
    if (OR) {
      docs = docs.filter(doc => {
        const docRec = doc as unknown as Record<string, unknown>;
        return OR.some(orClause => {
          return Object.entries(orClause).every(([k, v]) => {
            if (v === null) return docRec[k] === null || docRec[k] === undefined;
            if (typeof v === 'object' && v !== null && 'gt' in v) {
              const docVal = docRec[k];
              if (docVal === null || docVal === undefined) return false;
              return (docVal as Date) > (v as { gt: Date }).gt;
            }
            return docRec[k] === v;
          });
        });
      });
    }

    if (docs.length === 0) return null;
    const apiKey = docs[0];

    // Hydrate agent + owner if requested
    if (opts.include?.agent) {
      const agent = await agentDb.findUnique({ id: apiKey.agentId });
      if (agent) {
        let owner: DbUser | null = null;
        if (typeof opts.include.agent === 'object' && opts.include.agent.include?.owner) {
          owner = await userDb.findUnique({ id: agent.ownerId });
        }
        return { ...apiKey, agent: { ...agent, owner } };
      }
    }

    return apiKey;
  },

  async findMany(opts?: {
    where?: Partial<DbAgentApiKey>;
    select?: Record<string, boolean>;
    orderBy?: Record<string, 'asc' | 'desc'>;
  }): Promise<DbAgentApiKey[]> {
    let q: admin.firestore.Query = collections.agentApiKeys;
    if (opts?.where) {
      for (const [k, v] of Object.entries(opts.where)) {
        if (v !== undefined) q = q.where(k, '==', v);
      }
    }
    if (opts?.orderBy) {
      for (const [f, d] of Object.entries(opts.orderBy)) q = q.orderBy(f, d);
    }
    const snap = await q.get();
    return snap.docs.map(d => docToRecord<DbAgentApiKey>(d));
  },

  async create(data: Omit<DbAgentApiKey, 'id' | 'createdAt'>): Promise<DbAgentApiKey> {
    const id = await nextId('agentApiKeys');
    const record: DbAgentApiKey = { id, ...data, createdAt: new Date() };
    await collections.agentApiKeys.doc(String(id)).set(record);
    return record;
  },

  async update(where: { id: number }, data: Partial<DbAgentApiKey>): Promise<DbAgentApiKey> {
    const snap = await collections.agentApiKeys.where('id', '==', where.id).limit(1).get();
    if (snap.empty) throw new Error('AgentApiKey not found');
    const ref = snap.docs[0].ref;
    await ref.update(data);
    const updated = await ref.get();
    return docToRecord<DbAgentApiKey>(updated);
  },

  async updateMany(where: { keyId?: string; agentId?: number }, data: Partial<DbAgentApiKey>): Promise<{ count: number }> {
    let q: admin.firestore.Query = collections.agentApiKeys;
    if (where.keyId) q = q.where('keyId', '==', where.keyId);
    if (where.agentId !== undefined) q = q.where('agentId', '==', where.agentId);
    const snap = await q.get();
    const batch = db.batch();
    snap.docs.forEach(doc => batch.update(doc.ref, data));
    await batch.commit();
    return { count: snap.size };
  },
};

// ═══════════════════════════════════════════════════════════
//  SESSION operations
// ═══════════════════════════════════════════════════════════

export const sessionDb = {
  async create(data: Omit<DbSession, 'id' | 'createdAt'>): Promise<DbSession> {
    const id = await nextId('sessions');
    const session: DbSession = { id, ...data, createdAt: new Date() };
    await collections.sessions.doc(String(id)).set(session);
    return session;
  },

  async findUnique(where: { sessionId: string }): Promise<DbSession | null> {
    const snap = await collections.sessions.where('sessionId', '==', where.sessionId).limit(1).get();
    if (snap.empty) return null;
    return docToRecord<DbSession>(snap.docs[0]);
  },

  async delete(where: { sessionId: string }): Promise<void> {
    const snap = await collections.sessions.where('sessionId', '==', where.sessionId).limit(1).get();
    if (!snap.empty) await snap.docs[0].ref.delete();
  },
};

// ═══════════════════════════════════════════════════════════
//  Unified "prisma-like" export for easy migration
// ═══════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════
//  CHAT SESSION & CHAT MESSAGE (mobile_frontend)
// ═══════════════════════════════════════════════════════════

export interface DbChatSession {
  id: string;
  wallet: string | null;
  title: string | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface DbChatMessage {
  id: string;
  sessionId: string;
  role: string;
  text: string;
  createdAt: Date;
}

function getChatSessions() { return db.collection('chatSessions'); }
function getChatMessages() { return db.collection('chatMessages'); }

function generateCuid(): string {
  // Simple cuid-like ID: timestamp + random
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 10);
  return `c${ts}${rand}`;
}

export const chatSessionDb = {
  async findMany(opts?: {
    where?: Partial<DbChatSession>;
    orderBy?: Record<string, 'asc' | 'desc'>;
    take?: number;
  }): Promise<DbChatSession[]> {
    let q: admin.firestore.Query = getChatSessions();
    if (opts?.where) {
      for (const [k, v] of Object.entries(opts.where)) {
        if (v !== undefined) q = q.where(k, '==', v);
      }
    }
    if (opts?.orderBy) {
      for (const [f, d] of Object.entries(opts.orderBy)) q = q.orderBy(f, d);
    }
    if (opts?.take) q = q.limit(opts.take);
    const snap = await q.get();
    return snap.docs.map(d => docToRecord<DbChatSession>(d));
  },

  async upsert(
    where: { id: string },
    update: Partial<DbChatSession>,
    create: Omit<DbChatSession, 'createdAt' | 'updatedAt'>,
  ): Promise<DbChatSession> {
    const ref = getChatSessions().doc(where.id);
    const snap = await ref.get();
    const now = new Date();
    if (snap.exists) {
      await ref.update({ ...update, updatedAt: now });
      const updated = await ref.get();
      return docToRecord<DbChatSession>(updated);
    }
    const session: DbChatSession = {
      ...create,
      createdAt: now,
      updatedAt: now,
    };
    await ref.set(session);
    return session;
  },
};

export const chatMessageDb = {
  async create(data: Omit<DbChatMessage, 'id' | 'createdAt'>): Promise<DbChatMessage> {
    const id = generateCuid();
    const message: DbChatMessage = {
      id,
      sessionId: data.sessionId,
      role: data.role,
      text: data.text,
      createdAt: new Date(),
    };
    await getChatMessages().doc(id).set(message);
    return message;
  },

  async findMany(opts?: {
    where?: Partial<DbChatMessage>;
    orderBy?: Record<string, 'asc' | 'desc'>;
    take?: number;
  }): Promise<DbChatMessage[]> {
    let q: admin.firestore.Query = getChatMessages();
    if (opts?.where) {
      for (const [k, v] of Object.entries(opts.where)) {
        if (v !== undefined) q = q.where(k, '==', v);
      }
    }
    if (opts?.orderBy) {
      for (const [f, d] of Object.entries(opts.orderBy)) q = q.orderBy(f, d);
    }
    if (opts?.take) q = q.limit(opts.take);
    const snap = await q.get();
    return snap.docs.map(d => docToRecord<DbChatMessage>(d));
  },
};

export const firestoreDb = {
  user: userDb,
  agent: agentDb,
  order: orderDb,
  callSummary: callSummaryDb,
  marketplaceJob: marketplaceJobDb,
  userProfile: userProfileDb,
  agentDataRequest: agentDataRequestDb,
  agentJobUpdate: agentJobUpdateDb,
  agentApiKey: agentApiKeyDb,
  session: sessionDb,
  chatSession: chatSessionDb,
  chatMessage: chatMessageDb,
};

// Re-export the raw Firestore instance for advanced queries
export { db as firestore };
