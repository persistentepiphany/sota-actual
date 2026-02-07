"use client";

import React, { useEffect, useState, useCallback } from "react";

// ─── Types ───────────────────────────────────────────────────

interface Job {
  job_id: string;
  description: string;
  tags: string[];
  budget_usdc: number;
  status: string;
  poster: string;
  posted_at: number;
  deadline_ts: number;
  metadata: Record<string, any>;
}

interface Bid {
  bid_id: string;
  bidder_id: string;
  bidder_address: string;
  amount_usdc: number;
  estimated_seconds: number;
  tags: string[];
  submitted_at: number;
}

interface Worker {
  worker_id: string;
  address: string;
  tags: string[];
  max_concurrent: number;
  active_jobs: number;
}

// ─── Constants ───────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_BUTLER_API_URL || "http://localhost:3001";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  selecting: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  assigned: "bg-sky-500/20 text-sky-400 border-sky-500/30",
  expired: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
  cancelled: "bg-red-500/20 text-red-400 border-red-500/30",
};

// ─── Helpers ─────────────────────────────────────────────────

function timeAgo(ts: number) {
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function shortAddr(addr: string) {
  if (!addr || addr.length < 10) return addr || "—";
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

// ─── Components ──────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] || STATUS_COLORS.open;
  return (
    <span className={`text-[11px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${cls}`}>
      {status}
    </span>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string | number; icon: string }) {
  return (
    <div className="glass-card p-5 rounded-2xl flex items-center gap-4">
      <div className="text-3xl">{icon}</div>
      <div>
        <div className="text-2xl font-bold text-white">{value}</div>
        <div className="text-xs text-zinc-400 mt-0.5">{label}</div>
      </div>
    </div>
  );
}

function JobCard({ job, onSelect, selected }: { job: Job; onSelect: (id: string) => void; selected: boolean }) {
  return (
    <button
      onClick={() => onSelect(job.job_id)}
      className={`w-full text-left glass-card rounded-2xl p-5 transition-all duration-200 hover:ring-1 hover:ring-cyan-500/40 ${
        selected ? "ring-2 ring-cyan-400/60" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-white truncate">{job.description}</div>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {job.tags.map((t) => (
              <span key={t} className="text-[10px] bg-white/5 text-zinc-300 border border-white/10 px-2 py-0.5 rounded-full">
                {t}
              </span>
            ))}
          </div>
        </div>
        <StatusBadge status={job.status} />
      </div>

      <div className="flex items-center gap-4 mt-4 text-[11px] text-zinc-500">
        <span>💰 ${job.budget_usdc.toFixed(2)}</span>
        <span>👤 {shortAddr(job.poster)}</span>
        <span>🕐 {timeAgo(job.posted_at)}</span>
      </div>
    </button>
  );
}

function BidRow({ bid }: { bid: Bid }) {
  return (
    <div className="glass-card rounded-xl p-4 flex items-center justify-between">
      <div>
        <div className="text-sm font-medium text-white">{bid.bidder_id}</div>
        <div className="text-[11px] text-zinc-500 mt-0.5">{shortAddr(bid.bidder_address)}</div>
      </div>
      <div className="text-right">
        <div className="text-sm font-bold text-emerald-400">${bid.amount_usdc.toFixed(2)}</div>
        <div className="text-[11px] text-zinc-500">ETA {Math.ceil(bid.estimated_seconds / 60)} min</div>
      </div>
    </div>
  );
}

function WorkerRow({ worker }: { worker: Worker }) {
  return (
    <div className="glass-card rounded-xl p-4 flex items-center justify-between">
      <div>
        <div className="text-sm font-medium text-white">{worker.worker_id}</div>
        <div className="text-[11px] text-zinc-500 mt-0.5">{shortAddr(worker.address)}</div>
      </div>
      <div className="flex flex-wrap gap-1 justify-end">
        {worker.tags.map((t) => (
          <span key={t} className="text-[10px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-2 py-0.5 rounded-full">
            {t}
          </span>
        ))}
      </div>
      <div className="text-right ml-4 shrink-0">
        <div className="text-xs text-zinc-400">
          {worker.active_jobs}/{worker.max_concurrent}
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────

export default function MarketplacePage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [bids, setBids] = useState<Bid[]>([]);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"jobs" | "workers">("jobs");

  // Fetch jobs + workers
  const fetchAll = useCallback(async () => {
    try {
      const [jobsRes, workersRes] = await Promise.all([
        fetch(`${API}/api/flare/marketplace/jobs`),
        fetch(`${API}/api/flare/marketplace/workers`),
      ]);
      const jobsData = await jobsRes.json();
      const workersData = await workersRes.json();
      setJobs(jobsData.jobs || []);
      setWorkers(workersData.workers || []);
      setError(null);
    } catch (e: any) {
      setError(`Failed to connect to API at ${API}`);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch bids when a job is selected
  useEffect(() => {
    if (!selectedJob) {
      setBids([]);
      return;
    }
    fetch(`${API}/api/flare/marketplace/bids/${selectedJob}`)
      .then((r) => r.json())
      .then((d) => setBids(d.bids || []))
      .catch(() => setBids([]));
  }, [selectedJob]);

  // Auto-refresh every 5s
  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 5000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const openJobs = jobs.filter((j) => j.status === "open").length;
  const assignedJobs = jobs.filter((j) => j.status === "assigned").length;

  return (
    <div className="min-h-screen bg-[#020617]">
      {/* Header */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#020617]/80 border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <a href="/" className="text-zinc-400 hover:text-white transition text-sm">← Butler</a>
            <div className="w-px h-5 bg-white/10" />
            <h1 className="text-lg font-bold text-white tracking-tight">
              SOTA <span className="text-cyan-400">Marketplace</span>
            </h1>
            <span className="text-[10px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-2 py-0.5 rounded-full font-medium">
              Flare Coston2
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${error ? "bg-red-500" : "bg-emerald-500"} animate-pulse`} />
            <span className="text-[11px] text-zinc-500">{error ? "Disconnected" : "Live"}</span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard icon="📋" label="Total Jobs" value={jobs.length} />
          <StatCard icon="🟢" label="Open" value={openJobs} />
          <StatCard icon="⚡" label="In Progress" value={assignedJobs} />
          <StatCard icon="🤖" label="Workers Online" value={workers.length} />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-white/5 p-1 rounded-xl w-fit">
          <button
            onClick={() => setTab("jobs")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === "jobs" ? "bg-cyan-500/20 text-cyan-400" : "text-zinc-400 hover:text-white"
            }`}
          >
            Jobs ({jobs.length})
          </button>
          <button
            onClick={() => setTab("workers")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === "workers" ? "bg-cyan-500/20 text-cyan-400" : "text-zinc-400 hover:text-white"
            }`}
          >
            Workers ({workers.length})
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div className="text-center py-20 text-zinc-500">
            <div className="inline-block w-6 h-6 border-2 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin mb-4" />
            <div className="text-sm">Connecting to marketplace…</div>
          </div>
        ) : error ? (
          <div className="text-center py-20">
            <div className="text-red-400 text-sm">{error}</div>
            <button onClick={fetchAll} className="mt-4 text-xs text-cyan-400 hover:underline">
              Retry
            </button>
          </div>
        ) : tab === "jobs" ? (
          <div className="grid md:grid-cols-5 gap-6">
            {/* Job list */}
            <div className="md:col-span-3 space-y-3">
              {jobs.length === 0 ? (
                <div className="text-center py-16 glass-card rounded-2xl">
                  <div className="text-4xl mb-3">🏪</div>
                  <div className="text-sm text-zinc-400">No jobs yet</div>
                  <div className="text-[11px] text-zinc-600 mt-1">
                    Jobs posted through the Butler will appear here
                  </div>
                </div>
              ) : (
                jobs.map((j) => (
                  <JobCard key={j.job_id} job={j} onSelect={setSelectedJob} selected={selectedJob === j.job_id} />
                ))
              )}
            </div>

            {/* Bid detail panel */}
            <div className="md:col-span-2">
              <div className="sticky top-24 glass-card rounded-2xl p-5">
                {selectedJob ? (
                  <>
                    <h3 className="text-sm font-semibold text-white mb-1">Bids for {selectedJob.slice(0, 8)}</h3>
                    <div className="text-[11px] text-zinc-500 mb-4">
                      {bids.length} bid{bids.length !== 1 ? "s" : ""} received
                    </div>
                    <div className="space-y-2">
                      {bids.length === 0 ? (
                        <div className="text-xs text-zinc-600 text-center py-6">No bids yet</div>
                      ) : (
                        bids.map((b) => <BidRow key={b.bid_id} bid={b} />)
                      )}
                    </div>
                  </>
                ) : (
                  <div className="text-center py-8">
                    <div className="text-2xl mb-2">👈</div>
                    <div className="text-xs text-zinc-500">Select a job to view bids</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* Workers tab */
          <div className="max-w-2xl space-y-3">
            {workers.length === 0 ? (
              <div className="text-center py-16 glass-card rounded-2xl">
                <div className="text-4xl mb-3">🤖</div>
                <div className="text-sm text-zinc-400">No workers registered</div>
                <div className="text-[11px] text-zinc-600 mt-1">
                  Worker agents will appear here when they come online
                </div>
              </div>
            ) : (
              workers.map((w) => <WorkerRow key={w.worker_id} worker={w} />)
            )}
          </div>
        )}
      </main>
    </div>
  );
}
