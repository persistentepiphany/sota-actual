import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export interface Stage {
  id: string;
  name: string;
  description: string;
  status: "complete" | "in_progress" | "pending";
}

export interface DashboardTask {
  id: string;
  jobId: string;
  title: string;
  description: string;
  status: "executing" | "queued" | "completed" | "failed";
  progress: number;
  agent: string;
  agentIcon: string;
  tags: string[];
  createdAt: string;
  stages: Stage[];
}

export async function GET() {
  try {
    // Fetch marketplace jobs from DB
    const jobs = await prisma.marketplaceJob.findMany({
      orderBy: { createdAt: 'desc' },
      include: {
        updates: {
          orderBy: { createdAt: 'desc' },
          take: 1,
        },
      },
    }) as Awaited<ReturnType<typeof prisma.marketplaceJob.findMany>>;

    // Also fetch agent data requests to show pending communications
    const dataRequests = await prisma.agentDataRequest.findMany({
      where: { status: 'pending' },
      orderBy: { createdAt: 'desc' },
    });

    // Transform jobs to dashboard format
    const tasks: DashboardTask[] = jobs.map((job) => {
      // Parse metadata for additional info
      const metadata = job.metadata as Record<string, unknown> || {};
      
      // Map job status to dashboard status
      let status: DashboardTask["status"] = "queued";
      let progress = typeof metadata.progress === "number" ? metadata.progress : 0;
      
      switch (job.status) {
        case "open":
        case "selecting":
          status = "queued";
          break;
        case "assigned":
          status = "executing";
          if (progress === 0) progress = 25;
          break;
        case "completed":
          status = "completed";
          progress = 100;
          break;
        case "expired":
        case "cancelled":
          status = "failed";
          break;
        default:
          status = "queued";
      }

      // Get latest update for more accurate progress
      const latestUpdate = job.updates?.[0];
      if (latestUpdate) {
        if (latestUpdate.status === "in_progress") {
          status = "executing";
          if (progress === 0) progress = 50;
        } else if (latestUpdate.status === "completed") {
          status = "completed";
          progress = 100;
        } else if (latestUpdate.status === "error") {
          status = "failed";
        }
      }

      // Generate stages based on task status
      const stages = generateStages(status, progress, job.winner || "Agent");

      return {
        id: job.id.toString(),
        jobId: job.jobId,
        title: generateTitle(job.description, job.tags),
        description: job.description,
        status,
        progress,
        agent: job.winner || "Pending",
        agentIcon: getAgentIcon(job.winner),
        tags: job.tags || [],
        createdAt: job.createdAt.toISOString(),
        stages,
      };
    });

    // Group by status
    const executing = tasks.filter(t => t.status === "executing");
    const queued = tasks.filter(t => t.status === "queued");
    const completed = tasks.filter(t => t.status === "completed");
    const failed = tasks.filter(t => t.status === "failed");

    // Get online agents count
    const agents = await prisma.agent.findMany({
      where: { status: { in: ['active', 'busy'] } },
    });

    return NextResponse.json({
      tasks,
      grouped: {
        executing,
        queued,
        completed,
        failed,
      },
      stats: {
        total: tasks.length,
        executing: executing.length,
        queued: queued.length,
        completed: completed.length,
        failed: failed.length,
        pendingRequests: dataRequests.length,
      },
      agents: agents.map(a => ({
        id: a.id,
        title: a.title,
        status: a.status,
        icon: a.icon || "Bot",
      })),
    });
  } catch (error) {
    console.error("Failed to fetch dashboard tasks:", error);
    return NextResponse.json(
      { error: "Failed to fetch tasks" },
      { status: 500 }
    );
  }
}

// Helper functions
function generateTitle(description: string, tags: string[]): string {
  // Generate a title from description or tags
  if (tags && tags.length > 0) {
    const tag = tags[0];
    return tag.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  }
  // Take first 50 chars of description
  return description.length > 50 
    ? description.substring(0, 50) + "..." 
    : description;
}

function getAgentIcon(agentName: string | null): string {
  if (!agentName) return "Bot";
  const name = agentName.toLowerCase();
  if (name.includes("caller")) return "Phone";
  if (name.includes("hackathon")) return "Calendar";
  if (name.includes("manager")) return "Briefcase";
  return "Bot";
}

function generateStages(
  taskStatus: "executing" | "queued" | "completed" | "failed",
  progress: number,
  agentName: string
): Stage[] {
  // Define base stages
  const stages: Stage[] = [
    {
      id: "planning",
      name: "Planning",
      description: "Defining scope and requirements for the task.",
      status: "pending",
    },
    {
      id: "bidding",
      name: "Bidding",
      description: `Selected ${agentName} for task execution.`,
      status: "pending",
    },
    {
      id: "executing",
      name: "Executing",
      description: `${agentName} is processing the task...`,
      status: "pending",
    },
    {
      id: "review",
      name: "Review",
      description: "Human review of findings and recommendations.",
      status: "pending",
    },
  ];

  // Update stage statuses based on task status and progress
  if (taskStatus === "queued") {
    // Planning in progress
    stages[0].status = "in_progress";
    stages[0].description = "Analyzing task requirements and preparing execution plan.";
  } else if (taskStatus === "executing") {
    stages[0].status = "complete";
    stages[0].description = "Defined scope and task requirements.";
    
    if (progress < 30) {
      stages[1].status = "in_progress";
      stages[1].description = `Selecting best agent for the task...`;
    } else if (progress < 80) {
      stages[1].status = "complete";
      stages[2].status = "in_progress";
      stages[2].description = `${agentName} gathering data and processing task...`;
    } else {
      stages[1].status = "complete";
      stages[2].status = "complete";
      stages[2].description = `${agentName} completed data processing.`;
      stages[3].status = "in_progress";
      stages[3].description = "Reviewing results and preparing final output.";
    }
  } else if (taskStatus === "completed") {
    stages[0].status = "complete";
    stages[0].description = "Scope and requirements defined successfully.";
    stages[1].status = "complete";
    stages[1].description = `${agentName} was selected and assigned.`;
    stages[2].status = "complete";
    stages[2].description = `${agentName} completed all task operations.`;
    stages[3].status = "complete";
    stages[3].description = "Review complete. Task finished successfully.";
  } else if (taskStatus === "failed") {
    stages[0].status = "complete";
    stages[0].description = "Task requirements were defined.";
    stages[1].status = "complete";
    stages[1].description = agentName !== "Agent" ? `${agentName} was assigned.` : "Agent selection attempted.";
    stages[2].status = "complete";
    stages[2].description = "Execution encountered an error.";
    stages[3].status = "pending";
    stages[3].description = "Task failed before review stage.";
  }

  return stages;
}
