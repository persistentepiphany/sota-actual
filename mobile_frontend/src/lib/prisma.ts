/**
 * Database access layer for mobile_frontend — now backed by Firebase Firestore.
 *
 * Re-exports the same `prisma` object from the main app's Firestore layer.
 */
import { firestoreDb } from '../../../src/lib/firestore';

export const prisma = firestoreDb;
