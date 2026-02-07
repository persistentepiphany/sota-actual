/**
 * Quick verification: read back all seeded data from Firestore.
 * Run:  npx tsx scripts/verify-firestore.ts
 */

import {
  userDb, agentDb, marketplaceJobDb, agentJobUpdateDb,
  agentDataRequestDb, userProfileDb, callSummaryDb,
} from '../src/lib/firestore';

async function verify() {
  console.log('🔍 Verifying Firestore data …\n');

  const users = await userDb.findMany();
  console.log(`👤 Users (${users.length}):`);
  users.forEach(u => console.log(`   ${u.id}: ${u.name} <${u.email}> role=${u.role}`));

  const agents = await agentDb.findMany({ orderBy: { id: 'asc' } });
  console.log(`\n🤖 Agents (${agents.length}):`);
  agents.forEach(a =>
    console.log(`   ${a.id}: ${a.title} [${a.status}] rep=${a.reputation} reqs=${a.totalRequests}/${a.successfulRequests} owner=${a.ownerId}`)
  );

  const jobs = await marketplaceJobDb.findMany({ orderBy: { createdAt: 'desc' } });
  console.log(`\n📋 Marketplace Jobs (${jobs.length}):`);
  jobs.forEach(j =>
    console.log(`   ${j.jobId.slice(0, 8)}… [${j.status}] budget=$${j.budgetUsdc} winner=${j.winner || '—'} tags=[${j.tags.join(', ')}]`)
  );

  const updates = await agentJobUpdateDb.findMany({ orderBy: { createdAt: 'desc' } });
  console.log(`\n📝 Job Updates (${updates.length}):`);
  updates.forEach(u =>
    console.log(`   job=${u.jobId.slice(0, 8)}… agent=${u.agent} status=${u.status}: ${u.message.slice(0, 60)}`)
  );

  const dataReqs = await agentDataRequestDb.findMany({ orderBy: { createdAt: 'desc' } });
  console.log(`\n❓ Data Requests (${dataReqs.length}):`);
  dataReqs.forEach(r =>
    console.log(`   ${r.requestId} [${r.status}] agent=${r.agent}: ${r.question.slice(0, 60)}`)
  );

  const profiles = await userProfileDb.findMany();
  console.log(`\n🪪 User Profiles (${profiles.length}):`);
  profiles.forEach(p =>
    console.log(`   ${p.userId}: ${p.fullName} (${p.email}) — ${p.bio?.slice(0, 50)}`)
  );

  const calls = await callSummaryDb.findMany({ orderBy: { createdAt: 'desc' } });
  console.log(`\n📞 Call Summaries (${calls.length}):`);
  calls.forEach(c =>
    console.log(`   ${c.callSid} [${c.status}] to=${c.toNumber}: ${c.summary?.slice(0, 60)}`)
  );

  console.log('\n✅ All Firestore collections verified!');
  process.exit(0);
}

verify().catch((err) => {
  console.error('❌ Verification failed:', err);
  process.exit(1);
});
