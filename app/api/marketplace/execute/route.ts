import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { validateApiKey, decryptApiKey } from '@/lib/auth';

// POST /api/marketplace/execute - Execute a job (called by marketplace when agent wins)
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

    if (!authResult.permissions.includes('execute')) {
      return NextResponse.json({ error: 'API key does not have execute permission' }, { status: 403 });
    }

    const body = await request.json();
    const { jobId, result, status = 'completed' } = body;

    if (!jobId) {
      return NextResponse.json({ error: 'jobId is required' }, { status: 400 });
    }

    const agent = authResult.agent;

    // Find the job
    const job = await prisma.marketplaceJob.findUnique({
      where: { jobId }
    });

    if (!job) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 });
    }

    // Verify this agent is assigned to the job
    if (job.winner !== agent.title && job.status !== 'assigned') {
      return NextResponse.json({ error: 'Agent is not assigned to this job' }, { status: 403 });
    }

    // Update job status
    await prisma.marketplaceJob.update({
      where: { jobId },
      data: {
        status: status === 'completed' ? 'completed' : 'assigned',
      }
    });

    // Record the execution update
    await prisma.agentJobUpdate.create({
      data: {
        jobId: job.jobId,
        agent: agent.title,
        status,
        message: status === 'completed' ? 'Job completed successfully' : 'Job execution in progress',
        data: result || null,
      }
    });

    // Update agent stats
    const isSuccess = status === 'completed';
    await prisma.agent.update({
      where: { id: agent.id },
      data: {
        totalRequests: { increment: 1 },
        successfulRequests: isSuccess ? { increment: 1 } : undefined,
      }
    });

    // If there's a webhook URL, notify the developer
    if (agent.webhookUrl) {
      try {
        // Get the developer's API key for authenticating the webhook call
        const webhookPayload = {
          event: 'job.executed',
          jobId: job.jobId,
          agentId: agent.id,
          status,
          result,
          timestamp: new Date().toISOString(),
        };

        // Fire and forget - don't await
        fetch(agent.webhookUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(webhookPayload),
        }).catch(err => {
          console.error('Webhook delivery failed:', err);
        });
      } catch (webhookError) {
        console.error('Error preparing webhook:', webhookError);
      }
    }

    return NextResponse.json({
      success: true,
      execution: {
        jobId,
        agentId: agent.id,
        status,
      },
      message: 'Job execution recorded'
    });
  } catch (error) {
    console.error('Error executing job:', error);
    return NextResponse.json({ error: 'Failed to execute job' }, { status: 500 });
  }
}
