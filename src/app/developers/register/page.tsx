"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const CAPABILITIES = [
  { id: "voice_call", label: "Voice Calls", icon: "📞" },
  { id: "web_scrape", label: "Web Scraping", icon: "🌐" },
  { id: "data_analysis", label: "Data Analysis", icon: "📊" },
  { id: "image_gen", label: "Image Generation", icon: "🎨" },
  { id: "code_exec", label: "Code Execution", icon: "💻" },
  { id: "blockchain", label: "Blockchain Ops", icon: "⛓️" },
];

const CATEGORIES = [
  "Automation",
  "Data Processing",
  "Communication",
  "Content Creation",
  "Research",
  "Analytics",
];

export default function DeveloperPortalPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [testResult, setTestResult] = useState<any>(null);

  const [formData, setFormData] = useState({
    title: "",
    description: "",
    category: "",
    priceUsd: "10",
    tags: "",
    apiEndpoint: "",
    apiKey: "",
    capabilities: [] as string[],
    webhookUrl: "",
    documentation: "",
  });

  const handleCapabilityToggle = (capId: string) => {
    setFormData((prev) => ({
      ...prev,
      capabilities: prev.capabilities.includes(capId)
        ? prev.capabilities.filter((c) => c !== capId)
        : [...prev.capabilities, capId],
    }));
  };

  const testEndpoint = async () => {
    setLoading(true);
    setError("");
    setTestResult(null);
    try {
      const res = await fetch(formData.apiEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${formData.apiKey}`,
        },
        body: JSON.stringify({
          test: true,
          message: "SOTA platform test request",
        }),
      });
      const data = await res.json();
      setTestResult({ success: res.ok, status: res.status, data });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...formData,
          capabilities: JSON.stringify(formData.capabilities),
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const { agent } = await res.json();
      router.push(`/agents/${agent.id}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-12">
      {/* Hero */}
      <section className="glass rounded-3xl px-8 py-10">
        <div className="mb-3 pill inline-flex">Developer Portal</div>
        <h1 className="text-3xl font-semibold text-[var(--foreground)]">
          Register Your AI Agent
        </h1>
        <p className="mt-2 max-w-3xl text-[var(--muted)]">
          Connect your AI agent to the SOTA marketplace. Developers pay you in
          FLR when they use your agent. All payments are handled via smart
          contracts with FTSO pricing and FDC verification.
        </p>
      </section>

      {/* Step Indicator */}
      <div className="flex items-center justify-center gap-2">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold ${
                s === step
                  ? "bg-[var(--accent)] text-white"
                  : s < step
                  ? "bg-green-500 text-white"
                  : "bg-gray-200 text-gray-500"
              }`}
            >
              {s < step ? "✓" : s}
            </div>
            {s < 3 && <div className="h-0.5 w-12 bg-gray-300" />}
          </div>
        ))}
      </div>

      {/* Step 1: Basic Info */}
      {step === 1 && (
        <section className="glass rounded-2xl p-6 space-y-5">
          <h2 className="text-xl font-semibold">Step 1: Basic Information</h2>

          <div>
            <label className="block text-sm font-medium mb-1">
              Agent Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm"
              placeholder="e.g., Web Scraper Pro"
              value={formData.title}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, title: e.target.value }))
              }
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Description <span className="text-red-500">*</span>
            </label>
            <textarea
              className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm"
              rows={4}
              placeholder="Describe what your agent does and its key features..."
              value={formData.description}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, description: e.target.value }))
              }
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Category</label>
              <select
                className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm"
                value={formData.category}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, category: e.target.value }))
                }
              >
                <option value="">Select category</option>
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Price (USD per use)
              </label>
              <input
                type="number"
                className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm"
                placeholder="10"
                value={formData.priceUsd}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, priceUsd: e.target.value }))
                }
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Tags (comma-separated)
            </label>
            <input
              type="text"
              className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm"
              placeholder="scraping, automation, data"
              value={formData.tags}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, tags: e.target.value }))
              }
            />
          </div>

          <button
            onClick={() => setStep(2)}
            disabled={!formData.title || !formData.description}
            className="btn-primary w-full"
          >
            Next: API Configuration →
          </button>
        </section>
      )}

      {/* Step 2: API Config */}
      {step === 2 && (
        <section className="glass rounded-2xl p-6 space-y-5">
          <h2 className="text-xl font-semibold">Step 2: API Configuration</h2>

          <div>
            <label className="block text-sm font-medium mb-1">
              API Endpoint <span className="text-red-500">*</span>
            </label>
            <input
              type="url"
              className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm font-mono"
              placeholder="https://api.youragent.com/v1/execute"
              value={formData.apiEndpoint}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, apiEndpoint: e.target.value }))
              }
            />
            <p className="mt-1 text-xs text-gray-500">
              Your agent will receive POST requests with job details
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              API Key (optional)
            </label>
            <input
              type="password"
              className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm font-mono"
              placeholder="Bearer token for authentication"
              value={formData.apiKey}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, apiKey: e.target.value }))
              }
            />
            <p className="mt-1 text-xs text-gray-500">
              Stored encrypted. Used in Authorization header.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Webhook URL (optional)
            </label>
            <input
              type="url"
              className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm font-mono"
              placeholder="https://api.youragent.com/webhook"
              value={formData.webhookUrl}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, webhookUrl: e.target.value }))
              }
            />
            <p className="mt-1 text-xs text-gray-500">
              We'll POST job status updates here
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Capabilities <span className="text-red-500">*</span>
            </label>
            <div className="grid grid-cols-2 gap-3">
              {CAPABILITIES.map((cap) => (
                <button
                  key={cap.id}
                  onClick={() => handleCapabilityToggle(cap.id)}
                  className={`flex items-center gap-2 rounded-lg border-2 px-4 py-3 text-left text-sm transition-all ${
                    formData.capabilities.includes(cap.id)
                      ? "border-[var(--accent)] bg-blue-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <span className="text-2xl">{cap.icon}</span>
                  <span className="font-medium">{cap.label}</span>
                  {formData.capabilities.includes(cap.id) && (
                    <span className="ml-auto text-green-600">✓</span>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-lg border-2 border-blue-200 bg-blue-50 p-4">
            <span className="text-2xl">🔍</span>
            <div className="flex-1">
              <p className="text-sm font-medium">Test Your Endpoint</p>
              <p className="text-xs text-gray-600">
                Send a test request to verify connectivity
              </p>
            </div>
            <button
              onClick={testEndpoint}
              disabled={!formData.apiEndpoint || loading}
              className="btn-secondary"
            >
              {loading ? "Testing..." : "Test Now"}
            </button>
          </div>

          {testResult && (
            <div
              className={`rounded-lg border-2 p-4 ${
                testResult.success
                  ? "border-green-200 bg-green-50"
                  : "border-red-200 bg-red-50"
              }`}
            >
              <p className="text-sm font-semibold">
                {testResult.success ? "✅ Test Passed" : "❌ Test Failed"}
              </p>
              <p className="text-xs text-gray-600 mt-1">
                Status: {testResult.status}
              </p>
              <pre className="mt-2 text-xs bg-white rounded p-2 overflow-auto max-h-32">
                {JSON.stringify(testResult.data, null, 2)}
              </pre>
            </div>
          )}

          {error && (
            <div className="rounded-lg border-2 border-red-200 bg-red-50 p-4">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="flex gap-3">
            <button onClick={() => setStep(1)} className="btn-secondary flex-1">
              ← Back
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={
                !formData.apiEndpoint || formData.capabilities.length === 0
              }
              className="btn-primary flex-1"
            >
              Next: Documentation →
            </button>
          </div>
        </section>
      )}

      {/* Step 3: Documentation & Submit */}
      {step === 3 && (
        <section className="glass rounded-2xl p-6 space-y-5">
          <h2 className="text-xl font-semibold">Step 3: Documentation & Submit</h2>

          <div>
            <label className="block text-sm font-medium mb-1">
              API Documentation (Markdown)
            </label>
            <textarea
              className="w-full rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-sm font-mono"
              rows={12}
              placeholder={`## Usage
Describe how to use your agent...

## Input Schema
\`\`\`json
{
  "prompt": "string",
  "options": {}
}
\`\`\`

## Response Format
\`\`\`json
{
  "result": "...",
  "status": "completed"
}
\`\`\``}
              value={formData.documentation}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  documentation: e.target.value,
                }))
              }
            />
          </div>

          <div className="rounded-lg border-2 border-yellow-200 bg-yellow-50 p-4">
            <p className="text-sm font-semibold">📋 Review Before Submitting</p>
            <div className="mt-2 space-y-1 text-xs text-gray-700">
              <p>• Name: <strong>{formData.title}</strong></p>
              <p>• Category: <strong>{formData.category || "—"}</strong></p>
              <p>• Price: <strong>${formData.priceUsd} USD per use</strong></p>
              <p>
                • Capabilities:{" "}
                <strong>{formData.capabilities.join(", ") || "—"}</strong>
              </p>
              <p>
                • API: <strong>{formData.apiEndpoint || "—"}</strong>
              </p>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border-2 border-red-200 bg-red-50 p-4">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="flex gap-3">
            <button onClick={() => setStep(2)} className="btn-secondary flex-1">
              ← Back
            </button>
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="btn-primary flex-1"
            >
              {loading ? "Submitting..." : "Submit for Review"}
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
