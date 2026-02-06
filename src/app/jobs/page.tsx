"use client";

import { useState } from "react";
import { chainDefaults } from "@/lib/contracts";

interface QuoteResult {
  budget_usd: number;
  flr_amount: number;
  flr_price_usd: number;
  message: string;
}

interface CreateResult {
  job_id: number;
  tx_hash: string;
  budget_usd: number;
  flr_locked: number;
  provider: string;
  message: string;
}

export default function JobsPage() {
  const [description, setDescription] = useState("");
  const [budgetUsd, setBudgetUsd] = useState("50");
  const [deadline, setDeadline] = useState("24");
  const [providerAddress, setProviderAddress] = useState("");

  const [quote, setQuote] = useState<QuoteResult | null>(null);
  const [createResult, setCreateResult] = useState<CreateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const apiUrl = chainDefaults.butlerApiUrl;

  async function handleQuote() {
    setLoading(true);
    setError("");
    setQuote(null);
    try {
      const res = await fetch(`${apiUrl}/api/flare/quote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ budget_usd: parseFloat(budgetUsd) }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data: QuoteResult = await res.json();
      setQuote(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    setLoading(true);
    setError("");
    setCreateResult(null);
    try {
      const res = await fetch(`${apiUrl}/api/flare/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          description,
          budget_usd: parseFloat(budgetUsd),
          deadline_seconds: parseInt(deadline) * 3600,
          provider_address: providerAddress || undefined,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data: CreateResult = await res.json();
      setCreateResult(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 pb-16 pt-10">
      <section className="glass rounded-3xl px-8 py-10">
        <div className="mb-3 pill inline-flex">FTSO-Powered Pricing</div>
        <h1 className="text-3xl font-semibold text-[var(--foreground)]">
          Create a Job
        </h1>
        <p className="mt-2 text-[var(--muted)]">
          Set your budget in USD — FTSO converts to FLR in real time.
          Payment is held in escrow and released only when FDC confirms delivery.
        </p>
      </section>

      {/* Job Form */}
      <section className="glass rounded-2xl p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium mb-1">Job Description</label>
          <textarea
            className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm"
            rows={3}
            placeholder="e.g. Book me a hotel near the Oxford AI Hackathon this weekend"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Budget (USD)</label>
            <input
              type="number"
              className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm"
              placeholder="50"
              value={budgetUsd}
              onChange={(e) => setBudgetUsd(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Deadline (hours)</label>
            <input
              type="number"
              className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm"
              placeholder="24"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">
            Provider Address <span className="text-[var(--muted)]">(optional)</span>
          </label>
          <input
            type="text"
            className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm font-mono"
            placeholder="0x..."
            value={providerAddress}
            onChange={(e) => setProviderAddress(e.target.value)}
          />
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <button
            onClick={handleQuote}
            disabled={loading}
            className="btn-secondary flex-1"
          >
            {loading ? "Fetching..." : "Get FTSO Quote"}
          </button>
          <button
            onClick={handleCreate}
            disabled={loading || !description}
            className="btn-primary flex-1"
          >
            {loading ? "Creating..." : "Create & Fund Job"}
          </button>
        </div>
      </section>

      {/* Quote Result */}
      {quote && (
        <section className="rounded-2xl border-2 border-blue-200 bg-blue-50 p-6">
          <h3 className="text-lg font-semibold mb-2">📊 FTSO Quote</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold">${quote.budget_usd}</div>
              <div className="text-sm text-gray-500">USD Budget</div>
            </div>
            <div>
              <div className="text-2xl font-bold">≈ {quote.flr_amount.toFixed(2)}</div>
              <div className="text-sm text-gray-500">FLR Equivalent</div>
            </div>
            <div>
              <div className="text-2xl font-bold">${quote.flr_price_usd.toFixed(4)}</div>
              <div className="text-sm text-gray-500">FLR/USD (FTSO)</div>
            </div>
          </div>
          <p className="mt-3 text-sm text-gray-600 text-center">{quote.message}</p>
        </section>
      )}

      {/* Create Result */}
      {createResult && (
        <section className="rounded-2xl border-2 border-green-200 bg-green-50 p-6">
          <h3 className="text-lg font-semibold mb-2">✅ Job Created</h3>
          <div className="space-y-2 text-sm">
            <p><strong>Job ID:</strong> #{createResult.job_id}</p>
            <p><strong>FLR Locked:</strong> {createResult.flr_locked.toFixed(2)} FLR (≈ ${createResult.budget_usd})</p>
            <p><strong>Provider:</strong> <span className="font-mono text-xs">{createResult.provider}</span></p>
            <p>
              <strong>Transaction:</strong>{" "}
              <a
                href={`${chainDefaults.blockExplorer}/tx/${createResult.tx_hash}`}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 underline font-mono text-xs"
              >
                {createResult.tx_hash.slice(0, 20)}...
              </a>
            </p>
          </div>
          <p className="mt-3 text-sm text-gray-600">{createResult.message}</p>
        </section>
      )}

      {/* Error */}
      {error && (
        <section className="rounded-2xl border-2 border-red-200 bg-red-50 p-6">
          <h3 className="text-lg font-semibold text-red-700 mb-1">Error</h3>
          <p className="text-sm text-red-600">{error}</p>
        </section>
      )}
    </main>
  );
}
