/**
 * Seed Firebase Firestore with initial data matching the Prisma schema.
 *
 * Run:  npx tsx scripts/seed-firestore.ts
 */

import { firebaseAdmin } from '../src/lib/firebase-admin';
import {
  userDb, agentDb, marketplaceJobDb, agentJobUpdateDb,
  agentDataRequestDb, userProfileDb, callSummaryDb,
  collections,
} from '../src/lib/firestore';
import * as admin from 'firebase-admin';
import { randomUUID } from 'crypto';

async function seed() {
  console.log('🌱 Seeding Firestore …\n');

  // ── 1. Users ──────────────────────────────────────────
  console.log('👤 Creating users …');
  const alice = await userDb.create({
    firebaseUid: null,
    email: 'alice@sota.dev',
    passwordHash: '',
    name: 'Alice',
    walletAddress: '0x1111111111111111111111111111111111111111',
    role: 'developer',
  });
  console.log(`   ✅ user ${alice.id}: ${alice.email}`);

  const bob = await userDb.create({
    firebaseUid: null,
    email: 'bob@sota.dev',
    passwordHash: '',
    name: 'Bob',
    walletAddress: '0x2222222222222222222222222222222222222222',
    role: 'developer',
  });
  console.log(`   ✅ user ${bob.id}: ${bob.email}`);

  // ── 2. Agents ─────────────────────────────────────────
  console.log('\n🤖 Creating agents …');

  const butler = await agentDb.create({
    title: 'Butler',
    description: 'Your AI concierge that orchestrates all agents. Manages task routing, data requests, and inter-agent communication.',
    category: 'orchestrator',
    priceUsd: 0,
    status: 'active',
    tags: 'orchestrator,routing,management',
    network: 'flare-coston2',
    ownerId: alice.id,
    isVerified: true,
    icon: 'Bot',
    capabilities: JSON.stringify(['task_routing', 'data_request', 'agent_communication']),
    reputation: 5.0,
    totalRequests: 42,
    successfulRequests: 40,
  });
  console.log(`   ✅ agent ${butler.id}: ${butler.title}`);

  const caller = await agentDb.create({
    title: 'Caller Agent',
    description: 'Makes outbound voice calls using Twilio, collects information, and reports back with structured summaries.',
    category: 'communication',
    priceUsd: 0.10,
    status: 'active',
    tags: 'voice_call,twilio,communication',
    network: 'flare-coston2',
    ownerId: alice.id,
    isVerified: true,
    icon: 'Phone',
    capabilities: JSON.stringify(['voice_call', 'data_collection']),
    minFeeUsdc: 0.05,
    reputation: 4.8,
    totalRequests: 25,
    successfulRequests: 23,
  });
  console.log(`   ✅ agent ${caller.id}: ${caller.title}`);

  const hackathonAgent = await agentDb.create({
    title: 'Hackathon Finder',
    description: 'Discovers upcoming hackathons, auto-fills registration forms, and tracks application status.',
    category: 'events',
    priceUsd: 0.05,
    status: 'active',
    tags: 'hackathon_registration,event_finder,web_scrape',
    network: 'flare-coston2',
    ownerId: bob.id,
    isVerified: true,
    icon: 'Calendar',
    capabilities: JSON.stringify(['web_scrape', 'form_fill', 'hackathon_registration']),
    minFeeUsdc: 0.02,
    reputation: 4.5,
    totalRequests: 15,
    successfulRequests: 14,
  });
  console.log(`   ✅ agent ${hackathonAgent.id}: ${hackathonAgent.title}`);

  const flarePredictor = await agentDb.create({
    title: 'Flare FTSO Predictor',
    description: 'Analyzes Flare FTSO price feeds and makes short-term price predictions with confidence intervals.',
    category: 'defi',
    priceUsd: 0.15,
    status: 'active',
    tags: 'ftso,price_prediction,flare,defi',
    network: 'flare-coston2',
    ownerId: bob.id,
    isVerified: true,
    icon: 'TrendingUp',
    capabilities: JSON.stringify(['ftso_price', 'prediction', 'data_analysis']),
    minFeeUsdc: 0.10,
    reputation: 4.2,
    totalRequests: 8,
    successfulRequests: 7,
  });
  console.log(`   ✅ agent ${flarePredictor.id}: ${flarePredictor.title}`);

  // ── 3. Marketplace Jobs ───────────────────────────────
  console.log('\n📋 Creating marketplace jobs …');

  const job1 = await marketplaceJobDb.create({
    jobId: randomUUID(),
    description: 'Find and register me for the next 3 upcoming blockchain hackathons in Q1 2026',
    tags: ['hackathon_registration', 'event_finder'],
    budgetUsdc: 1.50,
    status: 'completed',
    poster: alice.walletAddress,
    winner: hackathonAgent.title,
    winnerPrice: 0.50,
    metadata: { tool: 'hackathon_finder', progress: 100 },
  });
  console.log(`   ✅ job ${job1.jobId.slice(0, 8)}… — ${job1.status}`);

  const job2 = await marketplaceJobDb.create({
    jobId: randomUUID(),
    description: 'Call the venue at +1-555-0100 and confirm the event schedule for next week',
    tags: ['voice_call', 'data_collection'],
    budgetUsdc: 0.50,
    status: 'assigned',
    poster: bob.walletAddress,
    winner: caller.title,
    winnerPrice: 0.10,
    metadata: { tool: 'caller', progress: 50 },
  });
  console.log(`   ✅ job ${job2.jobId.slice(0, 8)}… — ${job2.status}`);

  const job3 = await marketplaceJobDb.create({
    jobId: randomUUID(),
    description: 'Analyze FLR/USD price feed for the next 24 hours and report prediction',
    tags: ['ftso', 'price_prediction'],
    budgetUsdc: 2.00,
    status: 'open',
    poster: alice.walletAddress,
    winner: null,
    winnerPrice: null,
    metadata: { tool: 'flare_predictor' },
  });
  console.log(`   ✅ job ${job3.jobId.slice(0, 8)}… — ${job3.status}`);

  // ── 4. Agent Job Updates ──────────────────────────────
  console.log('\n📝 Creating job updates …');

  await agentJobUpdateDb.create({
    jobId: job1.jobId,
    agent: hackathonAgent.title,
    status: 'completed',
    message: 'Found 3 hackathons and submitted registrations for all.',
    data: {
      hackathons: [
        { name: 'ETH Denver 2026', date: '2026-02-28' },
        { name: 'Flare Builder Jam', date: '2026-03-15' },
        { name: 'HackFS 2026', date: '2026-03-20' },
      ],
    },
  });

  await agentJobUpdateDb.create({
    jobId: job2.jobId,
    agent: caller.title,
    status: 'in_progress',
    message: 'Initiating call to +1-555-0100 …',
    data: null,
  });

  console.log('   ✅ 2 job updates');

  // ── 5. Agent Data Requests ────────────────────────────
  console.log('\n❓ Creating data requests …');

  await agentDataRequestDb.create({
    requestId: `dr_${randomUUID().slice(0, 8)}`,
    jobId: job2.jobId,
    agent: 'caller',
    dataType: 'user_profile',
    question: 'What name should I use when speaking with the venue?',
    fields: ['fullName', 'phone'],
    context: 'Need caller identity for the outbound call.',
    status: 'pending',
    answerData: null,
    answerMsg: null,
    answeredAt: null,
  });
  console.log('   ✅ 1 data request');

  // ── 6. User Profile ──────────────────────────────────
  console.log('\n🪪 Creating user profile …');

  await userProfileDb.upsert(
    { userId: 'default' },
    {},
    {
      userId: 'default',
      fullName: 'Alice Developer',
      email: 'alice@sota.dev',
      phone: '+1-555-0199',
      location: 'San Francisco, CA',
      skills: 'Solidity, TypeScript, Python',
      experienceLevel: 'Senior',
      githubUrl: 'https://github.com/alice-dev',
      linkedinUrl: 'https://linkedin.com/in/alice-dev',
      portfolioUrl: 'https://alice.dev',
      bio: 'Full-stack Web3 developer building on Flare.',
      preferences: { interests: ['defi', 'hackathons', 'ai-agents'] },
      extra: null,
    },
  );
  console.log('   ✅ default profile');

  // ── 7. Call Summary ───────────────────────────────────
  console.log('\n📞 Creating call summary …');

  await callSummaryDb.create({
    conversationId: 'conv_001',
    callSid: 'CA_test_0001',
    status: 'completed',
    summary: 'Confirmed event schedule: keynote at 10 AM, workshops from 1–4 PM.',
    toNumber: '+1-555-0100',
    jobId: job2.jobId,
    neofsUri: null,
    payload: { duration: 120, transcript: "Hello, I'm calling to confirm the event schedule..." },
  });
  console.log('   ✅ 1 call summary');

  // ── Done ──────────────────────────────────────────────
  console.log('\n🎉 Firestore seeded successfully!');
  console.log('\nCollections created:');
  console.log('  • users          (2 docs)');
  console.log('  • agents         (4 docs)');
  console.log('  • marketplaceJobs (3 docs)');
  console.log('  • agentJobUpdates (2 docs)');
  console.log('  • agentDataRequests (1 doc)');
  console.log('  • userProfiles   (1 doc)');
  console.log('  • callSummaries  (1 doc)');
  console.log('  • counters       (auto-increment trackers)');

  process.exit(0);
}

seed().catch((err) => {
  console.error('❌ Seed failed:', err);
  process.exit(1);
});
