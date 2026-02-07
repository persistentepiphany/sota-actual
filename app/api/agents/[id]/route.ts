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

    const agent = await prisma.agent.findUnique({ id: agentId });

    if (!agent) {
      return NextResponse.json({ error: 'Agent not found' }, { status: 404 });
    }

    const owner = await prisma.user.findUnique({ id: agent.ownerId });

    return NextResponse.json({
      agent: {
        id: agent.id,
        title: agent.title,
        description: agent.description,
        category: agent.category,
        priceUsd: agent.priceUsd,
        tags: agent.tags,
        icon: agent.icon,
        status: agent.status,
        isVerified: agent.isVerified,
        reputation: agent.reputation,
        totalRequests: agent.totalRequests,
        successfulRequests: agent.successfulRequests,
        capabilities: agent.capabilities,
        minFeeUsdc: agent.minFeeUsdc,
        maxConcurrent: agent.maxConcurrent,
        documentation: agent.documentation,
        onchainAddress: agent.onchainAddress,
        walletAddress: agent.walletAddress,
        ownerId: agent.ownerId,
        createdAt: agent.createdAt,
        owner: owner ? { id: owner.id, name: owner.name } : null,
      }
    });
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
    const existingAgent = await prisma.agent.findUnique({ id: agentId });

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

    const agent = await prisma.agent.update({ id: agentId }, updateData);

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
    const existingAgent = await prisma.agent.findUnique({ id: agentId });

    if (!existingAgent) {
      return NextResponse.json({ error: 'Agent not found' }, { status: 404 });
    }

    if (existingAgent.ownerId !== user.id) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    await prisma.agent.delete({ id: agentId });

    return NextResponse.json({ success: true, message: 'Agent deleted' });
  } catch (error) {
    console.error('Error deleting agent:', error);
    return NextResponse.json({ error: 'Failed to delete agent' }, { status: 500 });
  }
}
