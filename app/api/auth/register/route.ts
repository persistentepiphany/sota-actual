import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { hashPassword, createSessionToken } from '@/lib/auth';
import { authSchema } from '@/lib/validators';

// POST /api/auth/register - Register a new developer
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const validation = authSchema.safeParse(body);
    
    if (!validation.success) {
      return NextResponse.json({ 
        error: 'Validation failed', 
        details: validation.error.flatten() 
      }, { status: 400 });
    }

    const { email, password, name } = validation.data;

    // Check if user already exists
    const existingUser = await prisma.user.findUnique({ email });

    if (existingUser) {
      return NextResponse.json({ error: 'Email already registered' }, { status: 409 });
    }

    // Create user
    const user = await prisma.user.create({
      email,
      passwordHash: hashPassword(password),
      name: name || email.split('@')[0],
      role: 'developer',
      firebaseUid: null,
      walletAddress: null,
    });

    // Create session token
    const token = createSessionToken({
      userId: user.id,
      walletAddress: user.walletAddress || undefined,
    });

    return NextResponse.json({
      success: true,
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
      },
      token,
    }, { status: 201 });
  } catch (error) {
    console.error('Error registering user:', error);
    return NextResponse.json({ error: 'Failed to register' }, { status: 500 });
  }
}
