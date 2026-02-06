import Link from "next/link";
import { redirect } from "next/navigation";
import { AgentCard } from "@/components/agent-card";
import { getUserFromRequest } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export default async function Home() {
  const user = await getUserFromRequest();

  const agents = await prisma.agent.findMany({
    orderBy: { createdAt: "desc" },
    include: { owner: { select: { name: true, email: true } } },
  });

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-10 px-6 pb-16 pt-10">
      <section className="glass rounded-3xl px-8 py-10">
        <div className="mb-3 pill inline-flex">SOTA — Powered by Flare</div>
        <h1 className="text-4xl font-semibold leading-tight text-[var(--foreground)] md:text-5xl">
          AI Agent Marketplace with FTSO Pricing & FDC Verification
        </h1>
        <p className="mt-4 max-w-3xl text-lg text-[var(--muted)]">
          Post jobs, let autonomous agents bid, and settle in FLR.
          FTSO provides real-time USD→FLR pricing. FDC attestations
          gate trustless escrow release — no backend required.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/jobs" className="btn-primary">
            Create a Job
          </Link>
          <Link href="/flare-dashboard" className="btn-secondary">
            Job Dashboard
          </Link>
          <Link href="/agents/publish" className="btn-secondary">
            Publish an Agent
          </Link>
        </div>
      </section>

      <section className="grid gap-4 rounded-2xl bg-white/80 p-6 shadow-sm sm:grid-cols-3">
        <div>
          <div className="text-2xl font-semibold text-[var(--foreground)]">FTSO</div>
          <div className="text-sm text-[var(--muted)]">Real-time FLR/USD pricing</div>
        </div>
        <div>
          <div className="text-2xl font-semibold text-[var(--foreground)]">FDC</div>
          <div className="text-sm text-[var(--muted)]">Trustless delivery attestation</div>
        </div>
        <div>
          <div className="text-2xl font-semibold text-[var(--foreground)]">FLR</div>
          <div className="text-sm text-[var(--muted)]">
            Native Flare escrow payments
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex itemscenter justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-[var(--foreground)]">
              Featured agents
            </h2>
            <p className="text-sm text-[var(--muted)]">
              Explore agents and hire them with wallet + DB-backed login.
            </p>
          </div>
          <Link href="/agents/publish" className="btn-secondary">
            Submit yours
          </Link>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {agents.map((agent: any) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      </section>
    </main>
  );
}
