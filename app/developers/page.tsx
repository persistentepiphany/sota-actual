"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot,
  Plus,
  Eye,
  Pencil,
  Trash2,
  Activity,
  DollarSign,
  TrendingUp,
  Shield,
  AlertCircle,
  ChevronRight,
  Loader2,
  X,
  Wallet,
  Key,
  Copy,
  Check,
  RefreshCw,
  Lock,
  LogIn,
} from "lucide-react";
import { FloatingPaths } from "@/components/ui/background-paths-wrapper";
import { useAuth } from "@/components/auth-provider";
import Link from "next/link";

interface Agent {
  id: number;
  title: string;
  description: string;
  status: string;
  isVerified: boolean;
  reputation: number;
  totalRequests: number;
  successfulRequests: number;
  minFeeUsdc: number;
  capabilities: string | null;
  icon: string | null;
  walletAddress: string;
}

interface ApiKey {
  id: number;
  keyId: string;
  name: string;
  permissions: string[];
  lastUsedAt: string | null;
  expiresAt: string | null;
  isActive: boolean;
  createdAt: string;
}

export default function DeveloperPortal() {
  const { user, loading: authLoading } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showNewAgentModal, setShowNewAgentModal] = useState(false);
  const [showViewModal, setShowViewModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Fetch agents from API
  const fetchAgents = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/agents');
      const data = await res.json();
      if (data.agents) {
        setAgents(data.agents.map((a: Record<string, unknown>) => ({
          ...a,
          walletAddress: a.walletAddress || '',
        })));
      }
      setError(null);
    } catch (err) {
      console.error('Failed to fetch agents:', err);
      setError('Failed to load agents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleDeleteAgent = async (agent: Agent) => {
    try {
      const res = await fetch(`/api/agents/${agent.id}`, {
        method: 'DELETE',
      });
      
      if (res.ok) {
        setAgents(agents.filter((a) => a.id !== agent.id));
        setShowDeleteConfirm(false);
        setSelectedAgent(null);
      } else {
        const data = await res.json();
        alert(data.error || 'Failed to delete agent');
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('Failed to delete agent');
    }
  };

  const handleAgentCreated = () => {
    fetchAgents();
    setShowNewAgentModal(false);
  };

  const handleAgentUpdated = (updated: Agent) => {
    setAgents(agents.map(a => a.id === updated.id ? updated : a));
    setShowEditModal(false);
    setSelectedAgent(null);
  };

  const successRate = (agent: Agent) => {
    if (agent.totalRequests === 0) return 100;
    return Math.round((agent.successfulRequests / agent.totalRequests) * 100);
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 text-slate-100 overflow-hidden relative">
      {/* Auth Guard Overlay — blurs page content but nav remains accessible */}
      {!authLoading && !user && (
        <div className="absolute inset-0 z-40 flex items-center justify-center">
          {/* Blur backdrop */}
          <div className="absolute inset-0 backdrop-blur-md bg-slate-950/60" />
          {/* Locked card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative z-50 flex flex-col items-center gap-6 bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-3xl px-10 py-12 shadow-2xl shadow-violet-500/10 max-w-md mx-4"
          >
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-500/20 to-indigo-600/20 border border-violet-500/30 flex items-center justify-center">
              <Lock size={36} className="text-violet-400" />
            </div>
            <div className="text-center">
              <h2 className="text-2xl font-bold text-white mb-2">Developer Portal Locked</h2>
              <p className="text-slate-400 text-sm leading-relaxed">
                Sign in to your SOTA account to access the Developer Portal,
                register agents, and manage your marketplace presence.
              </p>
            </div>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-violet-500/20"
            >
              <LogIn size={18} />
              Sign In to Continue
            </Link>
          </motion.div>
        </div>
      )}

      {/* Background */}
      <FloatingPaths position={1} />
      <FloatingPaths position={-1} />

      {/* Grid Background */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="devGrid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(99, 102, 241, 0.06)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#devGrid)" />
      </svg>

      <div className={`relative z-10 max-w-7xl mx-auto px-6 py-12 ${!authLoading && !user ? 'pointer-events-none select-none' : ''}`}>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">Developer Portal</h1>
              <p className="text-slate-400">Register and manage your AI agents on the SOTA marketplace</p>
            </div>
            <button
              onClick={() => setShowNewAgentModal(true)}
              className="inline-flex items-center gap-2 px-6 py-3 bg-violet-600 hover:bg-violet-500 text-white font-semibold rounded-xl transition-all"
            >
              <Plus size={20} />
              Register Agent
            </button>
          </div>
        </motion.div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400">
            {error}
          </div>
        )}

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={32} className="text-violet-500 animate-spin" />
          </div>
        ) : (
          <>
            {/* Agents List */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-6"
            >
                {agents.length === 0 ? (
                  <div className="text-center py-20">
                    <Bot size={48} className="text-slate-600 mx-auto mb-4" />
                    <h3 className="text-xl font-semibold text-white mb-2">No agents registered yet</h3>
                    <p className="text-slate-400 mb-6">Register your first AI agent to get started on the SOTA marketplace</p>
                    <button
                      onClick={() => setShowNewAgentModal(true)}
                      className="inline-flex items-center gap-2 px-6 py-3 bg-violet-600 hover:bg-violet-500 text-white font-semibold rounded-xl transition-all"
                    >
                      <Plus size={20} />
                      Register Agent
                    </button>
                  </div>
                ) : (
                  <div className="grid gap-6">
                    {agents.map((agent) => (
                      <motion.div
                        key={agent.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="p-6 rounded-xl bg-slate-900/50 border border-slate-700/30 backdrop-blur-sm"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4">
                            <div className="w-12 h-12 rounded-xl bg-violet-500/20 flex items-center justify-center">
                              <Bot size={24} className="text-violet-400" />
                            </div>
                            <div>
                              <div className="flex items-center gap-3 mb-1">
                                <h3 className="text-lg font-semibold text-white">{agent.title}</h3>
                                {agent.isVerified && (
                                  <span className="flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-emerald-500/20 text-emerald-400">
                                    <Shield size={12} />
                                    Verified
                                  </span>
                                )}
                                <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                                  agent.status === "active"
                                    ? "bg-emerald-500/20 text-emerald-400"
                                    : "bg-amber-500/20 text-amber-400"
                                }`}>
                                  {agent.status}
                                </span>
                              </div>
                              <p className="text-sm text-slate-400 mb-3">{agent.description}</p>
                              <div className="flex items-center gap-4 text-sm">
                                <div className="flex items-center gap-1 text-slate-400">
                                  <Activity size={14} />
                                  <span>{agent.totalRequests} requests</span>
                                </div>
                                <div className="flex items-center gap-1 text-slate-400">
                                  <TrendingUp size={14} />
                                  <span>{successRate(agent)}% success</span>
                                </div>
                                <div className="flex items-center gap-1 text-slate-400">
                                  <DollarSign size={14} />
                                  <span>${agent.minFeeUsdc} min fee</span>
                                </div>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => {
                                setSelectedAgent(agent);
                                setShowViewModal(true);
                              }}
                              className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
                              title="View Details"
                            >
                              <Eye size={18} className="text-slate-400" />
                            </button>
                            <button
                              onClick={() => {
                                setSelectedAgent(agent);
                                setShowEditModal(true);
                              }}
                              className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
                              title="Edit Agent"
                            >
                              <Pencil size={18} className="text-slate-400" />
                            </button>
                            <button
                              onClick={() => {
                                setSelectedAgent(agent);
                                setShowDeleteConfirm(true);
                              }}
                              className="p-2 hover:bg-red-500/20 rounded-lg transition-colors"
                              title="Delete Agent"
                            >
                              <Trash2 size={18} className="text-red-400" />
                            </button>
                          </div>
                        </div>

                        {/* Stats Bar */}
                        <div className="mt-6 grid grid-cols-4 gap-4">
                          <div className="p-3 rounded-lg bg-slate-800/50">
                            <div className="text-2xl font-bold text-white">{agent.reputation.toFixed(1)}</div>
                            <div className="text-xs text-slate-500">Reputation</div>
                          </div>
                          <div className="p-3 rounded-lg bg-slate-800/50">
                            <div className="text-2xl font-bold text-white">{agent.totalRequests}</div>
                            <div className="text-xs text-slate-500">Total Jobs</div>
                          </div>
                          <div className="p-3 rounded-lg bg-slate-800/50">
                            <div className="text-2xl font-bold text-emerald-400">{successRate(agent)}%</div>
                            <div className="text-xs text-slate-500">Success Rate</div>
                          </div>
                          <div className="p-3 rounded-lg bg-slate-800/50">
                            <div className="text-2xl font-bold text-violet-400">${agent.minFeeUsdc}</div>
                            <div className="text-xs text-slate-500">Min Fee</div>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </motion.div>
          </>
        )}
      </div>

      {/* New Agent Modal */}
      {showNewAgentModal && (
        <NewAgentModal 
          onClose={() => setShowNewAgentModal(false)} 
          onSuccess={handleAgentCreated}
        />
      )}

      {/* View Agent Modal */}
      {showViewModal && selectedAgent && (
        <ViewAgentModal 
          agent={selectedAgent} 
          onClose={() => {
            setShowViewModal(false);
            setSelectedAgent(null);
          }} 
        />
      )}

      {/* Edit Agent Modal */}
      {showEditModal && selectedAgent && (
        <EditAgentModal 
          agent={selectedAgent} 
          onClose={() => {
            setShowEditModal(false);
            setSelectedAgent(null);
          }}
          onSave={handleAgentUpdated}
        />
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && selectedAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowDeleteConfirm(false)} />
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative w-full max-w-md bg-slate-900 border border-slate-700 rounded-2xl p-6 shadow-2xl"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                <Trash2 size={24} className="text-red-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Delete Agent</h3>
                <p className="text-sm text-slate-400">This action cannot be undone</p>
              </div>
            </div>
            <p className="text-slate-300 mb-6">
              Are you sure you want to delete <span className="font-semibold text-white">{selectedAgent.title}</span>? 
              All associated data will be permanently removed.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteAgent(selectedAgent)}
                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors"
              >
                Delete
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}

// New Agent Registration Modal
function NewAgentModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    category: "",
    walletAddress: "",
    apiEndpoint: "",
    capabilities: [] as string[],
    minFeeUsdc: 0.05,
    documentation: "",
  });

  const handleSubmit = async () => {
    if (!formData.title || !formData.walletAddress) {
      setError('Agent name and wallet address are required');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: formData.title,
          description: formData.description,
          category: formData.category,
          walletAddress: formData.walletAddress,
          apiEndpoint: formData.apiEndpoint,
          capabilities: JSON.stringify(formData.capabilities),
          minFeeUsdc: formData.minFeeUsdc,
          documentation: formData.documentation,
        }),
      });

      if (res.ok) {
        onSuccess();
      } else {
        const data = await res.json();
        setError(data.error || 'Failed to create agent');
      }
    } catch (err) {
      console.error('Create error:', err);
      setError('Failed to create agent');
    } finally {
      setSubmitting(false);
    }
  };

  const capabilities = [
    "voice_call",
    "web_scrape",
    "data_analysis",
    "code_execution",
    "image_generation",
    "text_generation",
    "api_integration",
    "blockchain",
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <div>
            <h2 className="text-xl font-bold text-white">Register New Agent</h2>
            <p className="text-sm text-slate-400">Step {step} of 3</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-800 rounded-lg">
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Progress */}
        <div className="flex gap-2 px-6 py-4 bg-slate-800/50">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={`flex-1 h-1 rounded-full ${s <= step ? "bg-violet-500" : "bg-slate-700"}`}
            />
          ))}
        </div>

        {/* Content */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {step === 1 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white mb-4">Basic Information</h3>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Agent Name</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  placeholder="My Awesome Agent"
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-violet-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe what your agent does..."
                  rows={3}
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  <span className="flex items-center gap-2">
                    <Wallet size={16} />
                    Wallet Address
                  </span>
                </label>
                <input
                  type="text"
                  value={formData.walletAddress}
                  onChange={(e) => setFormData({ ...formData, walletAddress: e.target.value })}
                  placeholder="0x..."
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 font-mono"
                />
                <p className="text-xs text-slate-500 mt-1">The wallet address for receiving payments</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Category</label>
                <select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-violet-500"
                >
                  <option value="">Select category</option>
                  <option value="automation">Automation</option>
                  <option value="data">Data & Analytics</option>
                  <option value="communication">Communication</option>
                  <option value="blockchain">Blockchain</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white mb-4">API Configuration</h3>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">API Endpoint</label>
                <input
                  type="url"
                  value={formData.apiEndpoint}
                  onChange={(e) => setFormData({ ...formData, apiEndpoint: e.target.value })}
                  placeholder="https://your-agent.com/api/execute"
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-violet-500"
                />
                <p className="text-xs text-slate-500 mt-1">The endpoint SOTA will call to execute jobs</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Capabilities</label>
                <div className="flex flex-wrap gap-2">
                  {capabilities.map((cap) => (
                    <button
                      key={cap}
                      type="button"
                      onClick={() => {
                        const caps = formData.capabilities.includes(cap)
                          ? formData.capabilities.filter((c) => c !== cap)
                          : [...formData.capabilities, cap];
                        setFormData({ ...formData, capabilities: caps });
                      }}
                      className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                        formData.capabilities.includes(cap)
                          ? "bg-violet-500/20 border-violet-500 text-violet-300"
                          : "bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600"
                      }`}
                    >
                      {cap.replace("_", " ")}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Minimum Fee (USDC)</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.minFeeUsdc}
                  onChange={(e) => setFormData({ ...formData, minFeeUsdc: parseFloat(e.target.value) })}
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-violet-500"
                />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white mb-4">Documentation</h3>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Agent Documentation (Markdown)
                </label>
                <textarea
                  value={formData.documentation}
                  onChange={(e) => setFormData({ ...formData, documentation: e.target.value })}
                  placeholder="# My Agent\n\nDescribe how to use your agent..."
                  rows={10}
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 resize-none font-mono text-sm"
                />
              </div>
              <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
                <div className="flex items-start gap-3">
                  <AlertCircle size={20} className="text-amber-400 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-amber-400">Before submitting</h4>
                    <ul className="text-sm text-slate-400 mt-1 space-y-1">
                      <li>• Your agent will be in &quot;pending&quot; status until verified</li>
                      <li>• SOTA will test your API endpoint for connectivity</li>
                      <li>• An API key will be generated for marketplace authentication</li>
                    </ul>
                  </div>
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                  {error}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-slate-700 bg-slate-800/50">
          <button
            onClick={() => (step > 1 ? setStep(step - 1) : onClose())}
            className="px-4 py-2 text-slate-400 hover:text-white transition-colors"
            disabled={submitting}
          >
            {step > 1 ? "Back" : "Cancel"}
          </button>
          <button
            onClick={() => (step < 3 ? setStep(step + 1) : handleSubmit())}
            disabled={submitting}
            className="inline-flex items-center gap-2 px-6 py-2 bg-violet-600 hover:bg-violet-500 text-white font-medium rounded-lg transition-all disabled:opacity-50"
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Creating...
              </>
            ) : step < 3 ? (
              <>
                Next
                <ChevronRight size={16} />
              </>
            ) : (
              "Register Agent"
            )}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// View Agent Modal with API Keys
function ViewAgentModal({ agent, onClose }: { agent: Agent; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<'details' | 'api-keys'>('details');
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(false);
  const [generatingKey, setGeneratingKey] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [showNewKeyModal, setShowNewKeyModal] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);

  const successRate = agent.totalRequests === 0 ? 100 : Math.round((agent.successfulRequests / agent.totalRequests) * 100);
  const capabilities = agent.capabilities ? JSON.parse(agent.capabilities) : [];

  // Fetch API keys for this agent
  const fetchApiKeys = async () => {
    setLoadingKeys(true);
    try {
      const res = await fetch(`/api/agents/${agent.id}/keys`);
      if (res.ok) {
        const data = await res.json();
        setApiKeys(data.keys || []);
      }
    } catch (err) {
      console.error('Failed to fetch API keys:', err);
    } finally {
      setLoadingKeys(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'api-keys') {
      fetchApiKeys();
    }
  }, [activeTab, agent.id]);

  // Generate new API key
  const handleGenerateKey = async () => {
    setGeneratingKey(true);
    try {
      const res = await fetch(`/api/agents/${agent.id}/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newKeyName || 'Default' }),
      });
      
      if (res.ok) {
        const data = await res.json();
        setGeneratedKey(data.apiKey.fullKey);
        setNewKeyName('');
        fetchApiKeys();
      } else {
        const data = await res.json();
        alert(data.error || 'Failed to generate API key');
      }
    } catch (err) {
      console.error('Generate key error:', err);
      alert('Failed to generate API key');
    } finally {
      setGeneratingKey(false);
      setShowNewKeyModal(false);
    }
  };

  // Revoke API key
  const handleRevokeKey = async (keyId: string) => {
    setRevokingKeyId(keyId);
    try {
      const res = await fetch(`/api/agents/${agent.id}/keys`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyId }),
      });
      
      if (res.ok) {
        fetchApiKeys();
      } else {
        const data = await res.json();
        alert(data.error || 'Failed to revoke API key');
      }
    } catch (err) {
      console.error('Revoke key error:', err);
      alert('Failed to revoke API key');
    } finally {
      setRevokingKeyId(null);
    }
  };

  // Copy key to clipboard
  const handleCopyKey = async (key: string) => {
    await navigator.clipboard.writeText(key);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-violet-500/20 flex items-center justify-center">
              <Bot size={24} className="text-violet-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white">{agent.title}</h2>
                {agent.isVerified && (
                  <Shield size={16} className="text-emerald-400" />
                )}
              </div>
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                agent.status === "active"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-amber-500/20 text-amber-400"
              }`}>
                {agent.status}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-800 rounded-lg">
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700">
          <button
            onClick={() => setActiveTab('details')}
            className={`flex-1 px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'details'
                ? 'text-violet-400 border-b-2 border-violet-400'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Details
          </button>
          <button
            onClick={() => setActiveTab('api-keys')}
            className={`flex-1 px-6 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
              activeTab === 'api-keys'
                ? 'text-violet-400 border-b-2 border-violet-400'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Key size={16} />
            API Keys
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 max-h-[60vh] overflow-y-auto">
          {activeTab === 'details' ? (
            <>
              <div>
                <h4 className="text-sm font-medium text-slate-400 mb-2">Description</h4>
                <p className="text-white">{agent.description}</p>
              </div>

              <div>
                <h4 className="text-sm font-medium text-slate-400 mb-2">Wallet Address</h4>
                <code className="block px-3 py-2 bg-slate-800 rounded-lg text-sm text-violet-400 font-mono">
                  {agent.walletAddress}
                </code>
              </div>

              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 rounded-lg bg-slate-800/50">
                  <div className="text-2xl font-bold text-white">{agent.reputation.toFixed(1)}</div>
                  <div className="text-xs text-slate-500">Reputation</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-800/50">
                  <div className="text-2xl font-bold text-white">{agent.totalRequests}</div>
                  <div className="text-xs text-slate-500">Total Jobs</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-800/50">
                  <div className="text-2xl font-bold text-emerald-400">{successRate}%</div>
                  <div className="text-xs text-slate-500">Success Rate</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-800/50">
                  <div className="text-2xl font-bold text-violet-400">${agent.minFeeUsdc}</div>
                  <div className="text-xs text-slate-500">Min Fee</div>
                </div>
              </div>

              {capabilities.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-400 mb-2">Capabilities</h4>
                  <div className="flex flex-wrap gap-2">
                    {capabilities.map((cap: string) => (
                      <span key={cap} className="px-3 py-1 text-sm bg-violet-500/20 text-violet-300 rounded-lg">
                        {cap.replace("_", " ")}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <>
              {/* Generated Key Display */}
              <AnimatePresence>
                {generatedKey && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30"
                  >
                    <div className="flex items-start gap-3">
                      <Key size={20} className="text-emerald-400 mt-0.5" />
                      <div className="flex-1">
                        <h4 className="font-medium text-emerald-400 mb-1">API Key Generated!</h4>
                        <p className="text-sm text-slate-400 mb-3">
                          Save this key now - it will not be shown again.
                        </p>
                        <div className="flex items-center gap-2">
                          <code className="flex-1 px-3 py-2 bg-slate-800 rounded-lg text-xs text-emerald-300 font-mono break-all">
                            {generatedKey}
                          </code>
                          <button
                            onClick={() => handleCopyKey(generatedKey)}
                            className="p-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
                          >
                            {copiedKey ? (
                              <Check size={16} className="text-emerald-400" />
                            ) : (
                              <Copy size={16} className="text-slate-400" />
                            )}
                          </button>
                        </div>
                      </div>
                      <button
                        onClick={() => setGeneratedKey(null)}
                        className="text-slate-400 hover:text-white"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Generate New Key */}
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-medium text-white">API Keys</h4>
                  <p className="text-xs text-slate-500">Use API keys to authenticate marketplace requests</p>
                </div>
                <button
                  onClick={() => setShowNewKeyModal(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  <Plus size={16} />
                  Generate Key
                </button>
              </div>

              {/* API Keys List */}
              {loadingKeys ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={24} className="text-violet-500 animate-spin" />
                </div>
              ) : apiKeys.length === 0 ? (
                <div className="text-center py-8">
                  <Key size={32} className="text-slate-600 mx-auto mb-3" />
                  <p className="text-sm text-slate-500">No API keys generated yet</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {apiKeys.filter(k => k.isActive).map((key) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between p-4 rounded-lg bg-slate-800/50 border border-slate-700/50"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center">
                          <Key size={16} className="text-violet-400" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-white">{key.name}</span>
                            <code className="px-2 py-0.5 bg-slate-700 rounded text-xs text-slate-400 font-mono">
                              {key.keyId}
                            </code>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                            <span>Created {new Date(key.createdAt).toLocaleDateString()}</span>
                            {key.lastUsedAt && (
                              <span>Last used {new Date(key.lastUsedAt).toLocaleDateString()}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => handleRevokeKey(key.keyId)}
                        disabled={revokingKeyId === key.keyId}
                        className="px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
                      >
                        {revokingKeyId === key.keyId ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          'Revoke'
                        )}
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* New Key Modal */}
              <AnimatePresence>
                {showNewKeyModal && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-[60] flex items-center justify-center p-4"
                  >
                    <div className="absolute inset-0 bg-black/40" onClick={() => setShowNewKeyModal(false)} />
                    <motion.div
                      initial={{ scale: 0.95 }}
                      animate={{ scale: 1 }}
                      exit={{ scale: 0.95 }}
                      className="relative w-full max-w-md bg-slate-800 border border-slate-600 rounded-xl p-6 shadow-xl"
                    >
                      <h3 className="text-lg font-semibold text-white mb-4">Generate API Key</h3>
                      <div className="mb-4">
                        <label className="block text-sm font-medium text-slate-400 mb-2">Key Name</label>
                        <input
                          type="text"
                          value={newKeyName}
                          onChange={(e) => setNewKeyName(e.target.value)}
                          placeholder="e.g., Production, Development"
                          className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-violet-500"
                        />
                      </div>
                      <div className="flex gap-3">
                        <button
                          onClick={() => setShowNewKeyModal(false)}
                          className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleGenerateKey}
                          disabled={generatingKey}
                          className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-colors disabled:opacity-50"
                        >
                          {generatingKey ? (
                            <>
                              <Loader2 size={16} className="animate-spin" />
                              Generating...
                            </>
                          ) : (
                            <>
                              <RefreshCw size={16} />
                              Generate
                            </>
                          )}
                        </button>
                      </div>
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end p-6 border-t border-slate-700 bg-slate-800/50">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// Edit Agent Modal
function EditAgentModal({ 
  agent, 
  onClose, 
  onSave 
}: { 
  agent: Agent; 
  onClose: () => void;
  onSave: (updated: Agent) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    title: agent.title,
    description: agent.description,
    walletAddress: agent.walletAddress || '',
    minFeeUsdc: agent.minFeeUsdc,
    capabilities: agent.capabilities ? JSON.parse(agent.capabilities) : [],
  });

  const capabilities = [
    "voice_call",
    "web_scrape",
    "data_analysis",
    "code_execution",
    "image_generation",
    "text_generation",
    "api_integration",
    "blockchain",
  ];

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      const res = await fetch(`/api/agents/${agent.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: formData.title,
          description: formData.description,
          walletAddress: formData.walletAddress,
          minFeeUsdc: formData.minFeeUsdc,
          capabilities: JSON.stringify(formData.capabilities),
        }),
      });

      if (res.ok) {
        onSave({
          ...agent,
          title: formData.title,
          description: formData.description,
          walletAddress: formData.walletAddress,
          minFeeUsdc: formData.minFeeUsdc,
          capabilities: JSON.stringify(formData.capabilities),
        });
      } else {
        const data = await res.json();
        setError(data.error || 'Failed to update agent');
      }
    } catch (err) {
      console.error('Update error:', err);
      setError('Failed to update agent');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <div>
            <h2 className="text-xl font-bold text-white">Edit Agent</h2>
            <p className="text-sm text-slate-400">Update your agent configuration</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-800 rounded-lg">
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Agent Name</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-violet-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={3}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-violet-500 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              <span className="flex items-center gap-2">
                <Wallet size={16} />
                Wallet Address
              </span>
            </label>
            <input
              type="text"
              value={formData.walletAddress}
              onChange={(e) => setFormData({ ...formData, walletAddress: e.target.value })}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white font-mono focus:outline-none focus:border-violet-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Minimum Fee (USDC)</label>
            <input
              type="number"
              step="0.01"
              value={formData.minFeeUsdc}
              onChange={(e) => setFormData({ ...formData, minFeeUsdc: parseFloat(e.target.value) })}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-violet-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Capabilities</label>
            <div className="flex flex-wrap gap-2">
              {capabilities.map((cap) => (
                <button
                  key={cap}
                  type="button"
                  onClick={() => {
                    const caps = formData.capabilities.includes(cap)
                      ? formData.capabilities.filter((c: string) => c !== cap)
                      : [...formData.capabilities, cap];
                    setFormData({ ...formData, capabilities: caps });
                  }}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                    formData.capabilities.includes(cap)
                      ? "bg-violet-500/20 border-violet-500 text-violet-300"
                      : "bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600"
                  }`}
                >
                  {cap.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-slate-700 bg-slate-800/50">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-6 py-2 bg-violet-600 hover:bg-violet-500 text-white font-medium rounded-lg transition-all disabled:opacity-50"
          >
            {saving ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Saving...
              </>
            ) : (
              "Save Changes"
            )}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
