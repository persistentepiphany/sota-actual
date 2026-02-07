import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getCurrentUser, generateApiKey } from '@/lib/auth';

// GET /api/agents/[id]/keys - List API keys for an agent
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const user = await getCurrentUser(request);
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { id } = await params;
    const agentId = parseInt(id);
    
    if (isNaN(agentId)) {
      return NextResponse.json({ error: 'Invalid agent ID' }, { status: 400 });
    }

    // Check ownership
    const agent = await prisma.agent.findUnique({
      where: { id: agentId },
      select: { ownerId: true }
    });

    if (!agent) {
      return NextResponse.json({ error: 'Agent not found' }, { status: 404 });
    }

    if (agent.ownerId !== user.id) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    const keys = await prisma.agentApiKey.findMany({
      where: { agentId },
      select: {
        id: true,
        keyId: true,
        name: true,
        permissions: true,
        lastUsedAt: true,
        expiresAt: true,
        isActive: true,
        createdAt: true,
      },
      orderBy: { createdAt: 'desc' }
    });

    return NextResponse.json({ keys });
  } catch (error) {
    console.error('Error fetching API keys:', error);
    return NextResponse.json({ error: 'Failed to fetch API keys' }, { status: 500 });
  }
}

// POST /api/agents/[id]/keys - Create a new API key
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const user = await getCurrentUser(request);
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { id } = await params;
    const agentId = parseInt(id);
    
    if (isNaN(agentId)) {
      return NextResponse.json({ error: 'Invalid agent ID' }, { status: 400 });
    }

    // Check ownership
    const agent = await prisma.agent.findUnique({
      where: { id: agentId },
      select: { ownerId: true, title: true }
    });

    if (!agent) {
      return NextResponse.json({ error: 'Agent not found' }, { status: 404 });
    }

    if (agent.ownerId !== user.id) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    const body = await request.json();
    const { name = 'Default', permissions = ['execute', 'bid'], expiresInDays } = body;

    // Generate the API key
    const { keyId, fullKey, keyHash } = generateApiKey();

    // Calculate expiration
    let expiresAt: Date | null = null;
    if (expiresInDays && typeof expiresInDays === 'number') {
      expiresAt = new Date(Date.now() + expiresInDays * 24 * 60 * 60 * 1000);
    }

    // Create the key in database
    await prisma.agentApiKey.create({
      data: {
        keyId,
        keyHash,
        agentId,
        name,
        permissions,
        expiresAt,
      }
    });

    // Return the full key - this is the ONLY time it will be shown
    return NextResponse.json({
      success: true,
      apiKey: {
        keyId,
        fullKey, // Show once!
        name,
        permissions,
        expiresAt,
      },
      message: 'API key created. Save this key securely - it will not be shown again.'
    }, { status: 201 });
  } catch (error) {
    console.error('Error creating API key:', error);
    return NextResponse.json({ error: 'Failed to create API key' }, { status: 500 });
  }
}

// DELETE /api/agents/[id]/keys - Revoke an API key
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const user = await getCurrentUser(request);
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { id } = await params;
    const agentId = parseInt(id);
    
    if (isNaN(agentId)) {
      return NextResponse.json({ error: 'Invalid agent ID' }, { status: 400 });
    }

    // Check ownership
    const agent = await prisma.agent.findUnique({
      where: { id: agentId },
      select: { ownerId: true }
    });

    if (!agent) {
      return NextResponse.json({ error: 'Agent not found' }, { status: 404 });
    }

    if (agent.ownerId !== user.id) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    const body = await request.json();
    const { keyId } = body;

    if (!keyId) {
      return NextResponse.json({ error: 'keyId is required' }, { status: 400 });
    }

    // Revoke the key (soft delete by setting isActive = false)
    const key = await prisma.agentApiKey.updateMany({
      where: { 
        keyId,
        agentId 
      },
      data: { isActive: false }
    });

    if (key.count === 0) {
      return NextResponse.json({ error: 'API key not found' }, { status: 404 });
    }

    return NextResponse.json({ success: true, message: 'API key revoked' });
  } catch (error) {
    console.error('Error revoking API key:', error);
    return NextResponse.json({ error: 'Failed to revoke API key' }, { status: 500 });
  }
}
