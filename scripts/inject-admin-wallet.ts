/**
 * One-shot script: set all agents' owner to a single admin wallet,
 * and upsert the admin user account.
 *
 * Run:  npx tsx scripts/inject-admin-wallet.ts
 */

import { firebaseAdmin } from '../src/lib/firebase-admin';
import { userDb, agentDb, collections } from '../src/lib/firestore';
import { hashPassword } from '../src/lib/auth';

const ADMIN_WALLET = '0xc670ca2A23798BA5ee52dFfcEC86b3E220618225';
const ADMIN_EMAIL  = 'admin@gmail.com';
const ADMIN_PASS   = 'admin12345';
const ADMIN_NAME   = 'admin';

async function main() {
  console.log('--- inject-admin-wallet ---\n');

  // ── 1. Upsert admin user ──────────────────────────────
  console.log('Looking up existing user by email ...');
  let adminUser = await userDb.findUnique({ email: ADMIN_EMAIL });

  if (adminUser) {
    console.log(`  Found user id=${adminUser.id}, updating wallet + password ...`);
    adminUser = await userDb.update(
      { id: adminUser.id },
      {
        walletAddress: ADMIN_WALLET,
        passwordHash: hashPassword(ADMIN_PASS),
        name: ADMIN_NAME,
        role: 'developer',
      },
    );
  } else {
    console.log('  No existing user, creating ...');
    adminUser = await userDb.create({
      firebaseUid: null,
      email: ADMIN_EMAIL,
      passwordHash: hashPassword(ADMIN_PASS),
      name: ADMIN_NAME,
      walletAddress: ADMIN_WALLET,
      role: 'developer',
    });
  }
  console.log(`  Admin user id=${adminUser.id}  wallet=${adminUser.walletAddress}\n`);

  // ── 2. Update every agent to point to admin ───────────
  console.log('Fetching all agents ...');
  const allAgents = await agentDb.findMany();
  console.log(`  Found ${allAgents.length} agents\n`);

  for (const agent of allAgents) {
    console.log(`  Updating agent id=${agent.id} "${agent.title}" ...`);
    await agentDb.update(
      { id: agent.id },
      { ownerId: adminUser.id },
    );
    console.log(`    ownerId -> ${adminUser.id}`);
  }

  console.log(`\nDone! All ${allAgents.length} agents now owned by user ${adminUser.id} (${ADMIN_EMAIL} / ${ADMIN_WALLET})`);
  process.exit(0);
}

main().catch((err) => {
  console.error('Failed:', err);
  process.exit(1);
});
