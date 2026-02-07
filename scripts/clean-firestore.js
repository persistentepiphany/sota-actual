#!/usr/bin/env node
/**
 * One-time script: Delete all documents from marketplace-related Firestore collections.
 * Leaves agents, users, counters intact.
 *
 * Usage:
 *   node scripts/clean-firestore.js
 */

const admin = require("firebase-admin");
const path = require("path");
const fs = require("fs");

// Initialize Firebase Admin
const serviceAccountPath = path.join(__dirname, "..", "sota-firebase-sdk.json");
if (!fs.existsSync(serviceAccountPath)) {
  console.error("❌ sota-firebase-sdk.json not found at", serviceAccountPath);
  process.exit(1);
}
const serviceAccount = JSON.parse(fs.readFileSync(serviceAccountPath, "utf8"));
admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });

const db = admin.firestore();

async function deleteCollection(collectionName) {
  const snapshot = await db.collection(collectionName).get();
  if (snapshot.empty) {
    console.log(`  ${collectionName}: 0 docs (already empty)`);
    return 0;
  }

  const batch = db.batch();
  snapshot.docs.forEach((doc) => batch.delete(doc.ref));
  await batch.commit();
  console.log(`  ${collectionName}: ${snapshot.size} docs deleted`);
  return snapshot.size;
}

async function main() {
  console.log("🧹 Cleaning Firestore collections...\n");

  const collections = [
    "marketplaceJobs",
    "agentJobUpdates",
    "agentDataRequests",
  ];

  let total = 0;
  for (const col of collections) {
    total += await deleteCollection(col);
  }

  console.log(`\n✅ Done — ${total} documents deleted.`);
  console.log("   (agents, users, counters left intact)");
  process.exit(0);
}

main().catch((err) => {
  console.error("❌ Error:", err);
  process.exit(1);
});
