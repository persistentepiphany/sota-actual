import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

// ── Contract deployment addresses (Coston2 testnet) ──────────
const EXPLORER_BASE = "https://coston2-explorer.flare.network";
const CONTRACTS = {
  FlareOrderBook: "0x390413F0c7826523403760E086775DA9004aD004",
  FlareEscrow: "0x3b87ef622951c827F0730906A6F07ad6AB16A5C9",
  AgentRegistry: "0xc62a1e98543c42c475cd37e63188a29f098b35D4",
} as const;

// ── Interfaces ───────────────────────────────────────────────

export interface Stage {
  id: string;
  name: string;
  description: string;
  status: "complete" | "in_progress" | "pending";
}

export interface BidDetail {
  id: string;
  agent: string;
  agentId: number | null;
  agentIcon: string;
  price: number | null;
  priceFormatted: string;
  reputation: number;
  eta: string;
  isVerified: boolean;
  explorerLink: string | null;
  timestamp: string;
}

export interface WinnerInfo {
  agent: string;
  agentId: number | null;
  agentIcon: string;
  winnerPrice: number | null;
  winnerPriceFormatted: string;
  reputation: number;
  isVerified: boolean;
  explorerLink: string | null;
}

export interface ContractLinks {
  orderBook: string;
  escrow: string;
  agentRegistry: string;
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
  budgetUsdc: number | null;
  bids: BidDetail[];
  winner: WinnerInfo | null;
  contractLinks: ContractLinks;
}

export async function GET() {
  try {
    // Fetch marketplace jobs with ALL updates (no take limit)
    const jobs = await prisma.marketplaceJob.findMany({
      orderBy: { createdAt: 'desc' },
      include: {
        updates: {
          orderBy: { createdAt: 'desc' },
        },
      },
    }) as Awaited<ReturnType<typeof prisma.marketplaceJob.findMany>>;

    // Fetch all agents and build lookup maps
    const allAgents = await prisma.agent.findMany();
    const agentByTitle = new Map<string, typeof allAgents[0]>();
    const agentById = new Map<number, typeof allAgents[0]>();
    for (const a of allAgents) {
      agentByTitle.set(a.title.toLowerCase(), a);
      agentById.set(a.id, a);
    }

    // Also fetch agent data requests to show pending communications
    const dataRequests = await prisma.agentDataRequest.findMany({
      where: { status: 'pending' },
      orderBy: { createdAt: 'desc' },
    });

    // Contract links (same for all tasks)
    const contractLinks: ContractLinks = {
      orderBook: `${EXPLORER_BASE}/address/${CONTRACTS.FlareOrderBook}`,
      escrow: `${EXPLORER_BASE}/address/${CONTRACTS.FlareEscrow}`,
      agentRegistry: `${EXPLORER_BASE}/address/${CONTRACTS.AgentRegistry}`,
    };

    // Transform jobs to dashboard format
    const tasks: DashboardTask[] = jobs.map((job) => {
      const metadata = (job.metadata as Record<string, unknown>) || {};

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
      const updates = (job as typeof job & { updates?: Array<{ status: string }> }).updates || [];
      const latestUpdate = updates[0];
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

      // Extract bids from updates with status 'bid_submitted'
      const bids: BidDetail[] = updates
        .filter((u: { status: string }) => u.status === "bid_submitted")
        .map((u: { id?: number; agent: string; data?: Record<string, unknown> | null; createdAt: Date }, i: number) => {
          const matchedAgent = agentByTitle.get(u.agent.toLowerCase());
          const bidData = (u.data || {}) as Record<string, unknown>;
          const price = typeof bidData.price === "number" ? bidData.price : null;
          const eta = typeof bidData.eta === "string" ? bidData.eta : "~30s";

          return {
            id: `${job.id}-bid-${u.id ?? i}`,
            agent: matchedAgent?.title || u.agent,
            agentId: matchedAgent?.id ?? null,
            agentIcon: matchedAgent?.icon || "Bot",
            price,
            priceFormatted: price !== null ? `${price.toFixed(2)} USDC` : "Pending",
            reputation: matchedAgent?.reputation ?? 0,
            eta,
            isVerified: matchedAgent?.isVerified ?? false,
            explorerLink: matchedAgent?.walletAddress
              ? `${EXPLORER_BASE}/address/${matchedAgent.walletAddress}`
              : matchedAgent?.onchainAddress
                ? `${EXPLORER_BASE}/address/${matchedAgent.onchainAddress}`
                : null,
            timestamp: u.createdAt instanceof Date ? u.createdAt.toISOString() : new Date().toISOString(),
          };
        });

      // Build winner info
      let winner: WinnerInfo | null = null;
      if (job.winner) {
        const matchedWinner = agentByTitle.get(job.winner.toLowerCase());
        winner = {
          agent: matchedWinner?.title || job.winner,
          agentId: matchedWinner?.id ?? null,
          agentIcon: matchedWinner?.icon || "Bot",
          winnerPrice: job.winnerPrice ?? null,
          winnerPriceFormatted: job.winnerPrice !== null && job.winnerPrice !== undefined
            ? `${job.winnerPrice.toFixed(2)} USDC`
            : "N/A",
          reputation: matchedWinner?.reputation ?? 0,
          isVerified: matchedWinner?.isVerified ?? false,
          explorerLink: matchedWinner?.walletAddress
            ? `${EXPLORER_BASE}/address/${matchedWinner.walletAddress}`
            : matchedWinner?.onchainAddress
              ? `${EXPLORER_BASE}/address/${matchedWinner.onchainAddress}`
              : null,
        };
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
        createdAt: job.createdAt instanceof Date ? job.createdAt.toISOString() : new Date(job.createdAt).toISOString(),
        stages,
        budgetUsdc: job.budgetUsdc ?? null,
        bids,
        winner,
        contractLinks,
      };
    });

    // Group by status
    const executing = tasks.filter((t) => t.status === "executing");
    const queued = tasks.filter((t) => t.status === "queued");
    const completed = tasks.filter((t) => t.status === "completed");
    const failed = tasks.filter((t) => t.status === "failed");

    // Get online agents with extended info
    const activeAgents = allAgents.filter(
      (a) => a.status === "active" || a.status === "busy"
    );

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
      agents: activeAgents.map((a) => ({
        id: a.id,
        title: a.title,
        status: a.status,
        icon: a.icon || "Bot",
        walletAddress: a.walletAddress,
        reputation: a.reputation ?? 0,
        isVerified: a.isVerified ?? false,
        explorerLink: a.walletAddress
          ? `${EXPLORER_BASE}/address/${a.walletAddress}`
          : a.onchainAddress
            ? `${EXPLORER_BASE}/address/${a.onchainAddress}`
            : null,
      })),
      contractLinks,
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
  if (tags && tags.length > 0) {
    const tag = tags[0];
    return tag
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }
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

  if (taskStatus === "queued") {
    stages[0].status = "in_progress";
    stages[0].description =
      "Analyzing task requirements and preparing execution plan.";
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
    stages[1].description =
      agentName !== "Agent"
        ? `${agentName} was assigned.`
        : "Agent selection attempted.";
    stages[2].status = "complete";
    stages[2].description = "Execution encountered an error.";
    stages[3].status = "pending";
    stages[3].description = "Task failed before review stage.";
  }

  return stages;
}
