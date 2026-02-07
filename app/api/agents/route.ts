import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getCurrentUser } from '@/lib/auth';
import { agentSchema } from '@/lib/validators';

// GET /api/agents - List all agents (public, shows all statuses for transparency)
export async function GET() {
  try {
    const agents = await prisma.agent.findMany({
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
        walletAddress: true,
        ownerId: true,
        owner: {
          select: {
            id: true,
            name: true,
          }
        }
      },
      orderBy: { reputation: 'desc' }
    });

    return NextResponse.json({ agents });
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
      data: {
        title: data.title,
        description: data.description,
        category: data.category,
        priceUsd: data.priceUsd,
        tags: data.tags,
        network: data.network || 'flare-coston2',
        apiEndpoint: data.apiEndpoint,
        capabilities: data.capabilities,
        webhookUrl: data.webhookUrl,
        documentation: data.documentation,
        walletAddress: body.walletAddress as string || null,
        ownerId: user.id,
        status: 'pending', // Needs verification
        isVerified: false,
        minFeeUsdc: (body.minFeeUsdc as number) || 0.01,
        maxConcurrent: (body.maxConcurrent as number) || 5,
        bidAggressiveness: (body.bidAggressiveness as number) || 0.8,
        icon: body.icon || 'Bot',
      },
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
