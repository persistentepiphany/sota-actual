import * as admin from 'firebase-admin';
import * as path from 'path';
import * as fs from 'fs';

function getFirebaseAdmin(): admin.app.App {
  if (admin.apps.length > 0) {
    return admin.apps[0]!;
  }

  let serviceAccount: admin.ServiceAccount;

  // Prefer FIREBASE_SERVICE_ACCOUNT env var (for Vercel / CI)
  if (process.env.FIREBASE_SERVICE_ACCOUNT) {
    serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
  } else {
    const serviceAccountPath = path.join(process.cwd(), 'sota-firebase-sdk.json');
    serviceAccount = JSON.parse(fs.readFileSync(serviceAccountPath, 'utf8'));
  }

  return admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
  });
}

// Lazy initialization — only connect to Firebase when actually needed at runtime
let _firebaseAdmin: admin.app.App | null = null;
let _adminAuth: admin.auth.Auth | null = null;

export function getAdmin() {
  if (!_firebaseAdmin) {
    _firebaseAdmin = getFirebaseAdmin();
  }
  return _firebaseAdmin;
}

export function getAdminAuth() {
  if (!_adminAuth) {
    _adminAuth = admin.auth(getAdmin());
  }
  return _adminAuth;
}

// Keep backwards-compatible exports (getter-based so they're lazy)
export const firebaseAdmin = new Proxy({} as admin.app.App, {
  get(_, prop) {
    return (getAdmin() as any)[prop];
  },
});

export const adminAuth = new Proxy({} as admin.auth.Auth, {
  get(_, prop) {
    return (getAdminAuth() as any)[prop];
  },
});
