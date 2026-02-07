/**
 * Database access layer — now backed by Firebase Firestore.
 *
 * Every file that imports `prisma` from here will get the Firestore-backed
 * implementation whose API mirrors the Prisma models defined in
 * prisma/schema.prisma.
 *
 * Usage remains the same:
 *   import { prisma } from '@/lib/prisma';
 *   const users = await prisma.user.findMany();
 */
import { firestoreDb } from './firestore';

export const prisma = firestoreDb;
