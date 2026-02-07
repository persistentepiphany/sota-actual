import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export interface DashboardAgent {
  id: number;
  title: string;
  description: string;
  icon: string;
  status: "online" | "busy" | "offline";
  totalRequests: number;
  reputation: number;
  successRate: number;
  isButler: boolean;
}

export async function GET() {
  try {
    // Fetch all agents from DB
    const dbAgents = await prisma.agent.findMany({
      orderBy: { createdAt: "asc" },
    });

    // Transform to dashboard format
    const agents: DashboardAgent[] = dbAgents.map((agent) => {
      const totalReqs = (agent as { totalRequests?: number }).totalRequests ?? 0;
      const successReqs = (agent as { successfulRequests?: number }).successfulRequests ?? 0;
      const rep = (agent as { reputation?: number }).reputation ?? 5.0;
      const iconName = (agent as { icon?: string }).icon ?? "Bot";
      
      const successRate = totalReqs > 0 
        ? Math.round((successReqs / totalReqs) * 1000) / 10 
        : 100;
      
      // Determine status based on DB status field
      let status: "online" | "busy" | "offline" = "online";
      if (agent.status === "busy" || agent.status === "processing") {
        status = "busy";
      } else if (agent.status === "offline" || agent.status === "inactive") {
        status = "offline";
      }

      return {
        id: agent.id,
        title: agent.title,
        description: agent.description,
        icon: iconName,
        status,
        totalRequests: totalReqs,
        reputation: rep,
        successRate,
        isButler: agent.title.toLowerCase() === "butler",
      };
    });

    // Separate Butler from other agents
    const butler = agents.find(a => a.isButler) || {
      id: 0,
      title: "Butler",
      description: "Your AI concierge orchestrating all agents",
      icon: "Bot",
      status: "online" as const,
      totalRequests: 0,
      reputation: 5.0,
      successRate: 100,
      isButler: true,
    };

    const workerAgents = agents.filter(a => !a.isButler);

    return NextResponse.json({ 
      butler,
      agents: workerAgents,
      total: agents.length,
    });
  } catch (error) {
    console.error("Failed to fetch dashboard agents:", error);
    return NextResponse.json(
      { error: "Failed to fetch agents" },
      { status: 500 }
    );
  }
}
