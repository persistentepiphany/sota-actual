import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getCurrentUser } from '@/lib/auth';
import { agentSchema } from '@/lib/validators';

// GET /api/agents - List all agents (public, shows all statuses for transparency)
export async function GET() {
  try {
    const agents = await prisma.agent.findMany({
      orderBy: { reputation: 'desc' },
    });

    // Hydrate owner info
    const agentsWithOwner = await Promise.all(
      agents.map(async (agent) => {
        const owner = await prisma.user.findUnique({ id: agent.ownerId });
        return {
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
          walletAddress: agent.walletAddress,
          ownerId: agent.ownerId,
          owner: owner ? { id: owner.id, name: owner.name } : null,
        };
      })
    );

    return NextResponse.json({ agents: agentsWithOwner });
  } catch (error) {
    console.error('Error fetching agents:', error);
    return NextResponse.json({ error: 'Failed to fetch agents' }, { status: 500 });
  }
}

// POST /api/agents - Register a new agent (requires auth)
export async function POST(request: Request) {
  try {
    const user = await getCurrentUser(request);
    
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const validation = agentSchema.safeParse(body);
    
    if (!validation.success) {
      return NextResponse.json({ 
        error: 'Validation failed', 
        details: validation.error.flatten() 
      }, { status: 400 });
    }

    const data = validation.data;

    // Validate API endpoint if provided
    if (data.apiEndpoint) {
      try {
        const url = new URL(data.apiEndpoint);
        if (!['http:', 'https:'].includes(url.protocol)) {
          return NextResponse.json({ 
            error: 'API endpoint must use HTTP or HTTPS protocol' 
          }, { status: 400 });
        }
      } catch {
        return NextResponse.json({ 
          error: 'Invalid API endpoint URL' 
        }, { status: 400 });
      }
    }

    // Create the agent
    const agent = await prisma.agent.create({
      title: data.title,
      description: data.description,
      category: data.category ?? null,
      priceUsd: data.priceUsd,
      tags: data.tags ?? null,
      network: data.network || 'flare-coston2',
      apiEndpoint: data.apiEndpoint ?? null,
      capabilities: data.capabilities ?? null,
      webhookUrl: data.webhookUrl ?? null,
      documentation: data.documentation ?? null,
      walletAddress: (body.walletAddress as string) || null,
      ownerId: user.id,
      status: 'pending',
      isVerified: false,
      minFeeUsdc: (body.minFeeUsdc as number) || 0.01,
      maxConcurrent: (body.maxConcurrent as number) || 5,
      bidAggressiveness: (body.bidAggressiveness as number) || 0.8,
      icon: body.icon || 'Bot',
    });

    return NextResponse.json({ 
      success: true, 
      agent: {
        id: agent.id,
        title: agent.title,
        status: agent.status,
      },
      message: 'Agent registered successfully. Pending verification.'
    }, { status: 201 });

  } catch (error) {
    console.error('Error creating agent:', error);
    return NextResponse.json({ error: 'Failed to create agent' }, { status: 500 });
  }
}
