import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { agentSchema } from "@/lib/validators";
import { getUserFromRequest } from "@/lib/auth";

type RouteCtx = { params: Promise<{ id: string }> };

export async function GET(_: NextRequest, ctx: RouteCtx) {
  const { id: rawId } = await ctx.params;
  const id = Number(rawId);
  if (Number.isNaN(id)) {
    return NextResponse.json({ error: "Invalid id" }, { status: 400 });
  }

  const agent = await prisma.agent.findUnique({
    where: { id },
    include: {
      owner: { select: { id: true, email: true, name: true } },
    },
  });

  if (!agent) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  return NextResponse.json({ agent });
}

export async function PATCH(req: NextRequest, ctx: RouteCtx) {
  const user = await getUserFromRequest();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id: rawId } = await ctx.params;
  const body = await req.json();

  // Allow id either from the path param or body fallback to avoid NaN issues from the client.
  const pathId = Number(rawId);
  const bodyId = body?.id !== undefined ? Number(body.id) : NaN;
  const id = !Number.isNaN(pathId) ? pathId : bodyId;
  if (Number.isNaN(id)) {
    return NextResponse.json({ error: "Invalid id" }, { status: 400 });
  }

  const existing = await prisma.agent.findUnique({ where: { id } });
  if (!existing || existing.ownerId !== user.id) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const parsed = agentSchema.partial().safeParse({
    ...body,
    priceUsd: body.priceUsd !== undefined ? Number(body.priceUsd) : undefined,
  });

  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.flatten().fieldErrors },
      { status: 400 },
    );
  }

  const updated = await prisma.agent.update({
    where: { id },
    data: parsed.data,
  });

  return NextResponse.json({ agent: updated });
}

