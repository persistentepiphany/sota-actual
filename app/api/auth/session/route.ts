import { NextResponse } from 'next/server';
import { adminAuth } from '@/lib/firebase-admin';
import { prisma } from '@/lib/prisma';
import { cookies } from 'next/headers';

// POST /api/auth/session — Verify Firebase ID token, sync user to Prisma, set session cookie
export async function POST(request: Request) {
  try {
    const { idToken } = await request.json();

    if (!idToken) {
      return NextResponse.json({ error: 'ID token required' }, { status: 400 });
    }

    // Verify the Firebase ID token
    const decoded = await adminAuth.verifyIdToken(idToken);
    const { uid, email, name } = decoded;

    if (!email) {
      return NextResponse.json({ error: 'Email is required' }, { status: 400 });
    }

    // Upsert user in Prisma — create if first time, update if returning
    const user = await prisma.user.upsert({
      where: { firebaseUid: uid },
      update: {
        email,
        name: name || undefined,
      },
      create: {
        firebaseUid: uid,
        email,
        name: name || email.split('@')[0],
        passwordHash: '', // Not used with Firebase auth
        role: 'developer',
      },
    });

    // Create a session cookie (5 days)
    const expiresIn = 5 * 24 * 60 * 60 * 1000;
    const sessionCookie = await adminAuth.createSessionCookie(idToken, { expiresIn });

    const cookieStore = await cookies();
    cookieStore.set('__session', sessionCookie, {
      maxAge: expiresIn / 1000,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      path: '/',
      sameSite: 'lax',
    });

    return NextResponse.json({
      success: true,
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
        firebaseUid: user.firebaseUid,
      },
    });
  } catch (error) {
    console.error('Error creating session:', error);
    return NextResponse.json({ error: 'Failed to create session' }, { status: 401 });
  }
}

// DELETE /api/auth/session — Clear session cookie
export async function DELETE() {
  try {
    const cookieStore = await cookies();
    cookieStore.delete('__session');
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error clearing session:', error);
    return NextResponse.json({ error: 'Failed to clear session' }, { status: 500 });
  }
}
