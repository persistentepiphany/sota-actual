import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getCurrentUser } from '@/lib/auth';

// GET /api/agents/[id] - Get agent details
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const agentId = parseInt(id);
    
    if (isNaN(agentId)) {
      return NextResponse.json({ error: 'Invalid agent ID' }, { status: 400 });
    }

    const agent = await prisma.agent.findUnique({
      where: { id: agentId },
      select: {
        id: true,
        title: true,
        description: true,
        category: true,
        priceUsd: true,
        tags: true,
        icon: true,
        status: true,
        isVerified: true,
        reputation: true,
        totalRequests: true,
        successfulRequests: true,
        capabilities: true,
        minFeeUsdc: true,
        maxConcurrent: true,
        documentation: true,
        onchainAddress: true,
        walletAddress: true,
        ownerId: true,
        createdAt: true,
        owner: {
          select: {
            id: true,
            name: true,
          }
        }
      }
    });

    if (!agent) {
      return NextResponse.json({ error: 'Agent not found' }, { status: 404 });
    }

    return NextResponse.json({ agent });
  } catch (error) {
    console.error('Error fetching agent:', error);
    return NextResponse.json({ error: 'Failed to fetch agent' }, { status: 500 });
  }
}

// PATCH /api/agents/[id] - Update agent (owner only)
export async function PATCH(
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
    const existingAgent = await prisma.agent.findUnique({
      where: { id: agentId },
      select: { ownerId: true }
    });

    if (!existingAgent) {
      return NextResponse.json({ error: 'Agent not found' }, { status: 404 });
    }

    if (existingAgent.ownerId !== user.id) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    const body = await request.json();
    
    // Only allow updating certain fields
    const allowedFields = [
      'title', 'description', 'category', 'tags', 'apiEndpoint',
      'capabilities', 'webhookUrl', 'documentation', 'minFeeUsdc',
      'maxConcurrent', 'bidAggressiveness', 'icon', 'walletAddress'
    ];

    const updateData: Record<string, unknown> = {};
    for (const field of allowedFields) {
      if (body[field] !== undefined) {
        updateData[field] = body[field];
      }
    }

    const agent = await prisma.agent.update({
      where: { id: agentId },
      data: updateData,
    });

    return NextResponse.json({ 
      success: true, 
      agent: {
        id: agent.id,
        title: agent.title,
        status: agent.status,
      }
    });
  } catch (error) {
    console.error('Error updating agent:', error);
    return NextResponse.json({ error: 'Failed to update agent' }, { status: 500 });
  }
}

// DELETE /api/agents/[id] - Delete agent (owner only)
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
    const existingAgent = await prisma.agent.findUnique({
      where: { id: agentId },
      select: { ownerId: true }
    });

    if (!existingAgent) {
      return NextResponse.json({ error: 'Agent not found' }, { status: 404 });
    }

    if (existingAgent.ownerId !== user.id) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    await prisma.agent.delete({
      where: { id: agentId }
    });

    return NextResponse.json({ success: true, message: 'Agent deleted' });
  } catch (error) {
    console.error('Error deleting agent:', error);
    return NextResponse.json({ error: 'Failed to delete agent' }, { status: 500 });
  }
}
