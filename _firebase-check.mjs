import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const admin = require('firebase-admin');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config({ path: path.resolve('.env') });

const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
const app = admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
const db = admin.firestore();

const WALLET = '0xc670ca2A23798BA5ee52dFfcEC86b3E220618225';
const EMAIL = 'admin1@gmail.com';
const PASSWORD = 'Admin12345';
const NAME = 'admin';

// 1. Create Firebase Auth user
console.log('=== Creating Firebase Auth User ===');
let firebaseUid;
try {
  const authUser = await admin.auth().createUser({
    email: EMAIL,
    password: PASSWORD,
    displayName: NAME,
  });
  firebaseUid = authUser.uid;
  console.log(`  Created auth user: ${firebaseUid} | ${EMAIL}`);
} catch (e) {
  if (e.code === 'auth/email-already-exists') {
    const existing = await admin.auth().getUserByEmail(EMAIL);
    firebaseUid = existing.uid;
    console.log(`  Auth user already exists: ${firebaseUid} | ${EMAIL}`);
  } else {
    console.error('  Auth error:', e.message);
    process.exit(1);
  }
}

// 2. Get next user ID from counters
const counterRef = db.collection('counters').doc('users');
const counterDoc = await counterRef.get();
let nextUserId = 10; // fallback
if (counterDoc.exists) {
  nextUserId = counterDoc.data().value + 1;
}
const newUserDocId = String(nextUserId);

// 3. Create new Firestore user doc
console.log(`\n=== Creating Firestore User (doc ${newUserDocId}) ===`);
const newUserRef = db.collection('users').doc(newUserDocId);
await newUserRef.set({
  id: nextUserId,
  firebaseUid: firebaseUid,
  email: EMAIL,
  passwordHash: '',
  name: NAME,
  walletAddress: WALLET,
  role: 'developer',
  createdAt: admin.firestore.FieldValue.serverTimestamp(),
});
await counterRef.set({ value: nextUserId });
console.log(`  User ${newUserDocId}: ${EMAIL} | wallet=${WALLET} | firebaseUid=${firebaseUid}`);

// 4. Update all agents — set walletAddress and ownerId to new user
console.log('\n=== Updating all agents ===');
const agentIds = ['1', '2', '3', '4', '9'];
for (const id of agentIds) {
  const ref = db.collection('agents').doc(id);
  const doc = await ref.get();
  if (doc.exists) {
    const d = doc.data();
    await ref.update({
      walletAddress: WALLET,
      ownerId: nextUserId,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    });
    console.log(`  Agent ${id} "${d.title}": wallet=${WALLET}, ownerId=${nextUserId}`);
  }
}

// 5. Verify
console.log('\n=== Verification ===');
const agents = await db.collection('agents').orderBy('id').get();
for (const doc of agents.docs) {
  const d = doc.data();
  console.log(`  Agent ${doc.id} "${d.title}": wallet=${d.walletAddress}, ownerId=${d.ownerId}`);
}
const verifyUser = await newUserRef.get();
if (verifyUser.exists) {
  const u = verifyUser.data();
  console.log(`  User ${newUserDocId}: email=${u.email}, wallet=${u.walletAddress}, firebaseUid=${u.firebaseUid}`);
}

// List all auth users
console.log('\n=== All Auth Users ===');
const listResult = await admin.auth().listUsers(20);
for (const user of listResult.users) {
  console.log(`  ${user.uid} | ${user.email} | ${user.displayName || '(no name)'}`);
}

process.exit(0);
