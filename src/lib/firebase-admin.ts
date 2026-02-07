import * as admin from 'firebase-admin';
import * as path from 'path';
import * as fs from 'fs';

function getFirebaseAdmin(): admin.app.App {
  if (admin.apps.length > 0) {
    return admin.apps[0]!;
  }

  // Load service account from the JSON file in the project root
  const serviceAccountPath = path.join(process.cwd(), 'sota-firebase-sdk.json');
  const serviceAccount = JSON.parse(fs.readFileSync(serviceAccountPath, 'utf8'));

  return admin.initializeApp({
    credential: admin.credential.cert(serviceAccount as admin.ServiceAccount),
  });
}

export const firebaseAdmin = getFirebaseAdmin();
export const adminAuth = admin.auth(firebaseAdmin);
