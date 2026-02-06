"use client";

import { useState } from "react";
import { chainDefaults } from "@/lib/contracts";

interface JobStatus {
  job_id: number;
  status: string;
  poster: string;
  provider: string;
  metadata_uri: string;
  max_price_usd: number;
  max_price_flr: number;
  deadline: number;
  delivery_proof: string;
  escrow: {
    funded: boolean;
    released: boolean;
    refunded: boolean;
    amount_flr: number;
    usd_value: number;
  } | null;
  fdc_delivery_confirmed: boolean;
}

const STATUS_MAP: Record<string, { label: string; color: string; icon: string }> = {
  "0": { label: "OPEN", color: "bg-yellow-100 text-yellow-800", icon: "🟡" },
  "1": { label: "ASSIGNED", color: "bg-blue-100 text-blue-800", icon: "🔵" },
  "2": { label: "COMPLETED", color: "bg-purple-100 text-purple-800", icon: "🟣" },
  "3": { label: "RELEASED", color: "bg-green-100 text-green-800", icon: "🟢" },
  "4": { label: "CANCELLED", color: "bg-gray-100 text-gray-800", icon: "⚫" },
};

export default function FlareJobDashboard() {
  const [jobId, setJobId] = useState("1");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const apiUrl = chainDefaults.butlerApiUrl;

  async function fetchStatus() {
    setLoading(true);
    setError("");
    setJob(null);
    try {
      const res = await fetch(`${apiUrl}/api/flare/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: parseInt(jobId) }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data: JobStatus = await res.json();
      setJob(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function confirmDelivery() {
    setActionLoading(true);
    setError("");
    setSuccess("");
    try {
      const res = await fetch(`${apiUrl}/api/flare/demo/confirm-delivery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: parseInt(jobId) }),
      });
      if (!res.ok) throw new Error(await res.text());
      setSuccess("Delivery confirmed via FDC (demo mode).");
      fetchStatus();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function releasePayment() {
    setActionLoading(true);
    setError("");
    setSuccess("");
    try {
      const res = await fetch(`${apiUrl}/api/flare/release`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: parseInt(jobId) }),
      });
      if (!res.ok) throw new Error(await res.text());
      setSuccess("Payment released to provider!");
      fetchStatus();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActionLoading(false);
    }
  }

  const statusInfo = job ? STATUS_MAP[job.status] || STATUS_MAP["0"] : null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 pb-16 pt-10">
      <section className="glass rounded-3xl px-8 py-10">
        <div className="mb-3 pill inline-flex">FDC-Gated Escrow</div>
        <h1 className="text-3xl font-semibold text-[var(--foreground)]">
          Job Dashboard
        </h1>
        <p className="mt-2 text-[var(--muted)]">
          Track job status, view escrow details, and release payment once
          the Flare Data Connector confirms delivery.
        </p>
      </section>

      {/* Lookup */}
      <section className="glass rounded-2xl p-6">
        <div className="flex gap-3">
          <input
            type="number"
            className="flex-1 rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm"
            placeholder="Job ID"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
          />
          <button onClick={fetchStatus} disabled={loading} className="btn-primary">
            {loading ? "Loading..." : "Lookup Job"}
          </button>
        </div>
      </section>

      {/* Job Detail */}
      {job && statusInfo && (
        <>
          {/* Status Header */}
          <section className="glass rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Job #{job.job_id}</h2>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusInfo.color}`}>
                {statusInfo.icon} {statusInfo.label}
              </span>
            </div>

            {/* Progress Bar */}
            <div className="flex items-center gap-1 mb-6">
              {["OPEN", "ASSIGNED", "COMPLETED", "RELEASED"].map((step, i) => {
                const currentStep = parseInt(job.status);
                const isActive = i <= currentStep && currentStep < 4;
                const isDone = i < currentStep || currentStep === 3;
                return (
                  <div key={step} className="flex-1 flex flex-col items-center">
                    <div
                      className={`h-2 w-full rounded-full ${
                        isDone ? "bg-green-500" : isActive ? "bg-blue-500" : "bg-gray-200"
                      }`}
                    />
                    <span className="mt-1 text-xs text-gray-500">{step}</span>
                  </div>
                );
              })}
            </div>

            {/* Details Grid */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Poster</span>
                <p className="font-mono text-xs truncate">{job.poster}</p>
              </div>
              <div>
                <span className="text-gray-500">Provider</span>
                <p className="font-mono text-xs truncate">
                  {job.provider === "0x0000000000000000000000000000000000000000"
                    ? "Unassigned"
                    : job.provider}
                </p>
              </div>
              <div>
                <span className="text-gray-500">Max Price</span>
                <p>${job.max_price_usd} ≈ {job.max_price_flr.toFixed(2)} FLR</p>
              </div>
              <div>
                <span className="text-gray-500">Deadline</span>
                <p>{new Date(job.deadline * 1000).toLocaleString()}</p>
              </div>
              <div className="col-span-2">
                <span className="text-gray-500">Metadata</span>
                <p className="font-mono text-xs truncate">{job.metadata_uri || "—"}</p>
              </div>
            </div>
          </section>

          {/* Escrow Card */}
          {job.escrow && (
            <section className="rounded-2xl border-2 border-blue-200 bg-blue-50 p-6">
              <h3 className="text-lg font-semibold mb-3">💰 Escrow</h3>
              <div className="grid grid-cols-3 gap-4 text-center mb-4">
                <div>
                  <div className="text-2xl font-bold">{job.escrow.amount_flr.toFixed(2)}</div>
                  <div className="text-sm text-gray-500">FLR Locked</div>
                </div>
                <div>
                  <div className="text-2xl font-bold">${job.escrow.usd_value}</div>
                  <div className="text-sm text-gray-500">USD Value</div>
                </div>
                <div>
                  <div className="text-2xl font-bold">
                    {job.escrow.released ? "✅" : job.escrow.refunded ? "↩️" : "🔒"}
                  </div>
                  <div className="text-sm text-gray-500">
                    {job.escrow.released ? "Released" : job.escrow.refunded ? "Refunded" : "Held"}
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* FDC Attestation Card */}
          <section className="rounded-2xl border-2 border-purple-200 bg-purple-50 p-6">
            <h3 className="text-lg font-semibold mb-3">🔐 FDC Attestation</h3>
            <div className="flex items-center gap-3 mb-4">
              <span className="text-3xl">
                {job.fdc_delivery_confirmed ? "✅" : "⏳"}
              </span>
              <div>
                <p className="font-medium">
                  {job.fdc_delivery_confirmed
                    ? "Delivery Confirmed by Flare Data Connector"
                    : "Awaiting FDC Delivery Attestation"}
                </p>
                <p className="text-sm text-gray-500">
                  {job.fdc_delivery_confirmed
                    ? "The FDC Merkle proof verified that the agent completed the task."
                    : "Once the agent completes the task, an attestation will be submitted to FDC."}
                </p>
              </div>
            </div>

            {/* Actions */}
            {parseInt(job.status) >= 2 && !job.fdc_delivery_confirmed && (
              <button
                onClick={confirmDelivery}
                disabled={actionLoading}
                className="btn-secondary w-full mb-2"
              >
                {actionLoading ? "Confirming..." : "Confirm Delivery (Demo FDC)"}
              </button>
            )}

            {job.fdc_delivery_confirmed && job.escrow && !job.escrow.released && (
              <button
                onClick={releasePayment}
                disabled={actionLoading}
                className="btn-primary w-full"
              >
                {actionLoading ? "Releasing..." : "Release Payment to Provider"}
              </button>
            )}
          </section>

          {/* Delivery Proof */}
          {job.delivery_proof && job.delivery_proof !== "" && (
            <section className="glass rounded-2xl p-6">
              <h3 className="text-lg font-semibold mb-2">📋 Delivery Proof</h3>
              <p className="font-mono text-xs break-all bg-gray-100 rounded-lg p-3">
                {job.delivery_proof}
              </p>
            </section>
          )}

          {/* Explorer Link */}
          <a
            href={`${chainDefaults.blockExplorer}/address/${chainDefaults.flareOrderBook}`}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-blue-600 underline text-center"
          >
            View FlareOrderBook on Coston2 Explorer →
          </a>
        </>
      )}

      {/* Feedback */}
      {success && (
        <section className="rounded-2xl border-2 border-green-200 bg-green-50 p-4">
          <p className="text-sm text-green-700">✅ {success}</p>
        </section>
      )}
      {error && (
        <section className="rounded-2xl border-2 border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-600">❌ {error}</p>
        </section>
      )}
    </main>
  );
}
