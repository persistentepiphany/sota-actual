import { NextResponse } from 'next/server';
import { getCurrentUser } from '@/lib/auth';
import { adminAuth } from '@/lib/firebase-admin';
import { prisma } from '@/lib/prisma';
import { cookies } from 'next/headers';

// GET /api/auth/me - Get current user (supports both Firebase session cookie and legacy Bearer token)
export async function GET(request: Request) {
  try {
    // First try Firebase session cookie
    const cookieStore = await cookies();
    const sessionCookie = cookieStore.get('__session')?.value;

    if (sessionCookie) {
      try {
        const decoded = await adminAuth.verifySessionCookie(sessionCookie, true);
        const user = await prisma.user.findUnique({
          where: { firebaseUid: decoded.uid }
        });

        if (user) {
          return NextResponse.json({
            user: {
              id: user.id,
              email: user.email,
              name: user.name,
              role: user.role,
              walletAddress: user.walletAddress,
              firebaseUid: user.firebaseUid,
            }
          });
        }
      } catch {
        // Session cookie invalid or expired, fall through to legacy auth
      }
    }

    // Fallback to legacy Bearer token auth
    const user = await getCurrentUser(request);

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    return NextResponse.json({
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
        walletAddress: user.walletAddress,
      }
    });
  } catch (error) {
    console.error('Error getting user:', error);
    return NextResponse.json({ error: 'Failed to get user' }, { status: 500 });
  }
}
