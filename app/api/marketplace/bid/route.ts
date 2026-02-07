import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { validateApiKey, decryptApiKey } from '@/lib/auth';

// POST /api/marketplace/bid - Submit a bid for a job
export async function POST(request: Request) {
  try {
    const authHeader = request.headers.get('Authorization');
    
    if (!authHeader?.startsWith('ApiKey ')) {
      return NextResponse.json({ error: 'API key required' }, { status: 401 });
    }

    const apiKey = authHeader.slice(7);
    const authResult = await validateApiKey(apiKey);
    
    if (!authResult) {
      return NextResponse.json({ error: 'Invalid API key' }, { status: 401 });
    }

    if (!authResult.permissions.includes('bid')) {
      return NextResponse.json({ error: 'API key does not have bid permission' }, { status: 403 });
    }

    const body = await request.json();
    const { jobId, bidPrice, estimatedDuration, message } = body;

    if (!jobId || bidPrice === undefined) {
      return NextResponse.json({ error: 'jobId and bidPrice are required' }, { status: 400 });
    }

    const agent = authResult.agent;

    // Validate bid price against agent's minimum fee
    if (bidPrice < agent.minFeeUsdc) {
      return NextResponse.json({ 
        error: `Bid price must be at least ${agent.minFeeUsdc} USDC` 
      }, { status: 400 });
    }

    // Find the job
    const job = await prisma.marketplaceJob.findUnique({
      where: { jobId }
    });

    if (!job) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 });
    }

    if (job.status !== 'open' && job.status !== 'selecting') {
      return NextResponse.json({ error: 'Job is not accepting bids' }, { status: 400 });
    }

    // Record the bid as an update
    await prisma.agentJobUpdate.create({
      data: {
        jobId: job.jobId,
        agent: agent.title,
        status: 'bid_submitted',
        message: message || `Bid: ${bidPrice} USDC`,
        data: {
          agentId: agent.id,
          bidPrice,
          estimatedDuration,
          capabilities: agent.capabilities ? JSON.parse(agent.capabilities) : [],
          reputation: agent.reputation,
        }
      }
    });

    return NextResponse.json({
      success: true,
      bid: {
        jobId,
        agentId: agent.id,
        agentTitle: agent.title,
        bidPrice,
        estimatedDuration,
      },
      message: 'Bid submitted successfully'
    });
  } catch (error) {
    console.error('Error submitting bid:', error);
    return NextResponse.json({ error: 'Failed to submit bid' }, { status: 500 });
  }
}

// GET /api/marketplace/bid - Get available jobs for bidding
export async function GET(request: Request) {
  try {
    const authHeader = request.headers.get('Authorization');
    
    if (!authHeader?.startsWith('ApiKey ')) {
      return NextResponse.json({ error: 'API key required' }, { status: 401 });
    }

    const apiKey = authHeader.slice(7);
    const authResult = await validateApiKey(apiKey);
    
    if (!authResult) {
      return NextResponse.json({ error: 'Invalid API key' }, { status: 401 });
    }

    const agent = authResult.agent;
    const capabilities = agent.capabilities ? JSON.parse(agent.capabilities) : [];
    const agentTags = agent.tags?.split(',').map(t => t.trim()) || [];

    // Find open jobs that match agent's capabilities/tags
    const jobs = await prisma.marketplaceJob.findMany({
      where: {
        status: { in: ['open', 'selecting'] },
      },
      orderBy: { createdAt: 'desc' },
      take: 50,
    });

    // Filter jobs that match agent's tags
    const matchingJobs = jobs.filter(job => {
      if (job.tags.length === 0) return true;
      return job.tags.some(tag => 
        agentTags.includes(tag) || capabilities.includes(tag)
      );
    });

    return NextResponse.json({
      jobs: matchingJobs.map(job => ({
        jobId: job.jobId,
        description: job.description,
        tags: job.tags,
        budgetUsdc: job.budgetUsdc,
        status: job.status,
        createdAt: job.createdAt,
        metadata: job.metadata,
      }))
    });
  } catch (error) {
    console.error('Error fetching jobs:', error);
    return NextResponse.json({ error: 'Failed to fetch jobs' }, { status: 500 });
  }
}
