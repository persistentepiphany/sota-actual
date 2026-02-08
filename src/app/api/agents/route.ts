import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { agentSchema } from "@/lib/validators";
import { getCurrentUser } from "@/lib/auth";

export async function GET() {
  const agents = await prisma.agent.findMany({
    orderBy: { createdAt: 'desc' },
  });

  // Hydrate owner relation
  const agentsWithOwner = await Promise.all(
    agents.map(async (agent) => {
      const owner = await prisma.user.findUnique({ id: agent.ownerId });
      return { ...agent, owner: owner ? { id: owner.id, email: owner.email, name: owner.name } : null };
    })
  );

  return NextResponse.json({ agents: agentsWithOwner });
}

export async function POST(req: Request) {
  const user = await getCurrentUser(req);
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const parsed = agentSchema.safeParse({
    ...body,
    priceUsd: Number(body.priceUsd),
  });

  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.flatten().fieldErrors },
      { status: 400 },
    );
  }

  // Validate API endpoint if provided
  if (parsed.data.apiEndpoint) {
    try {
      const testUrl = new URL(parsed.data.apiEndpoint);
      if (!["http:", "https:"].includes(testUrl.protocol)) {
        return NextResponse.json(
          { error: "API endpoint must use HTTP or HTTPS protocol" },
          { status: 400 }
        );
      }
    } catch (error) {
      return NextResponse.json(
        { error: "Invalid API endpoint URL" },
        { status: 400 }
      );
    }
  }

  const agent = await prisma.agent.create({
    ...parsed.data,
    ownerId: user.id,
    tags: parsed.data.tags ?? null,
    isVerified: false,
  });

  return NextResponse.json({ agent });
}

