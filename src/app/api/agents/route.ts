import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { agentSchema } from "@/lib/validators";
import { getCurrentUser } from "@/lib/auth";

export async function GET() {
  const agents = await prisma.agent.findMany({
    orderBy: { createdAt: "desc" },
    include: { owner: { select: { id: true, email: true, name: true } } },
  });
  return NextResponse.json({ agents });
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
      // Basic check that it's http/https
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
    title: parsed.data.title,
    description: parsed.data.description,
    ownerId: user.id,
    tags: parsed.data.tags || "",
    isVerified: false,
  });

  return NextResponse.json({ agent });
}

