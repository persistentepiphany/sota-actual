"use client";
import React, { useState, useEffect, useCallback } from "react";
import {
  Bot,
  Phone,
  Calendar,
  Briefcase,
  Search,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  LayoutGrid,
  LayoutList,
  Zap,
  RefreshCw,
  X,
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  ArrowUpRight,
  ArrowDownRight,
  Gavel,
  Timer,
  Shield,
  BarChart3,
  type LucideIcon,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { FloatingPaths } from "@/components/ui/background-paths-wrapper";

// Icon mapping
const iconMap: Record<string, LucideIcon> = {
  Bot,
  Phone,
  Calendar,
  Briefcase,
};

interface Stage {
  id: string;
  name: string;
  description: string;
  status: "complete" | "in_progress" | "pending";
}

interface Task {
  id: string;
  jobId: string;
  title: string;
  description: string;
  status: "executing" | "queued" | "completed" | "failed";
  progress: number;
  agent: string;
  agentIcon: string;
  tags: string[];
  createdAt: string;
  stages: Stage[];
}

interface Agent {
  id: number;
  title: string;
  status: string;
  icon: string;
}

interface MarketplaceData {
  tasks: Task[];
  grouped: {
    executing: Task[];
    queued: Task[];
    completed: Task[];
    failed: Task[];
  };
  stats: {
    total: number;
    executing: number;
    queued: number;
    completed: number;
    failed: number;
  };
  agents: Agent[];
}

// Simulated bid data for the order book
interface Bid {
  id: string;
  agent: string;
  agentIcon: string;
  price: string;
  reputation: number;
  eta: string;
  timestamp: Date;
}

export default function Marketplace() {
  const [data, setData] = useState<MarketplaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"orderbook" | "grid">("orderbook");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [activeFilter, setActiveFilter] = useState<"all" | "bids" | "executing" | "settled">("all");
  const [recentExecutions, setRecentExecutions] = useState<Task[]>([]);

  // Fetch tasks from API
  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch("/api/tasks");
      if (!res.ok) throw new Error("Failed to fetch tasks");
      const json = await res.json();
      setData(json);
      
      // Update recent executions feed
      const completed = json.grouped?.completed || [];
      setRecentExecutions(completed.slice(0, 10));
      
      setError(null);
    } catch (err) {
      console.error("Error fetching tasks:", err);
      setError("Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 5000); // Faster refresh for real-time feel
    return () => clearInterval(interval);
  }, [fetchTasks]);

  // Filter tasks by search query and filter
  const filterTasks = (tasks: Task[]) => {
    return tasks.filter((task) => {
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matches =
          task.title.toLowerCase().includes(query) ||
          task.description.toLowerCase().includes(query) ||
          task.agent.toLowerCase().includes(query) ||
          task.tags.some((t) => t.toLowerCase().includes(query));
        if (!matches) return false;
      }
      return true;
    });
  };

  const getFilteredTasks = () => {
    if (!data?.tasks) return [];
    switch (activeFilter) {
      case "bids":
        return filterTasks(data.grouped.queued || []);
      case "executing":
        return filterTasks(data.grouped.executing || []);
      case "settled":
        return filterTasks([...(data.grouped.completed || []), ...(data.grouped.failed || [])]);
      default:
        return filterTasks(data.tasks);
    }
  };

  const filteredTasks = getFilteredTasks();

  const getIcon = (iconName: string): LucideIcon => iconMap[iconName] || Bot;

  const getStatusConfig = (status: string) => {
    switch (status) {
      case "executing":
        return {
          color: "text-amber-400",
          bg: "bg-amber-400/10",
          border: "border-amber-400/30",
          glow: "shadow-amber-500/20",
          label: "EXECUTING",
          icon: <Activity size={12} className="animate-pulse" />,
        };
      case "queued":
        return {
          color: "text-cyan-400",
          bg: "bg-cyan-400/10",
          border: "border-cyan-400/30",
          glow: "shadow-cyan-500/20",
          label: "OPEN BID",
          icon: <Gavel size={12} />,
        };
      case "completed":
        return {
          color: "text-emerald-400",
          bg: "bg-emerald-400/10",
          border: "border-emerald-400/30",
          glow: "shadow-emerald-500/20",
          label: "SETTLED",
          icon: <CheckCircle size={12} />,
        };
      case "failed":
        return {
          color: "text-red-400",
          bg: "bg-red-400/10",
          border: "border-red-400/30",
          glow: "shadow-red-500/20",
          label: "FAILED",
          icon: <XCircle size={12} />,
        };
      default:
        return {
          color: "text-slate-400",
          bg: "bg-slate-400/10",
          border: "border-slate-400/30",
          glow: "",
          label: status.toUpperCase(),
          icon: null,
        };
    }
  };

  // Generate mock bids for a task
  const generateBids = (task: Task): Bid[] => {
    if (task.status !== "queued") return [];
    const agents = ["Butler AI", "FlarePredictor", "TaskRunner", "DataBot"];
    return agents.slice(0, Math.floor(Math.random() * 3) + 1).map((agent, i) => ({
      id: `${task.id}-bid-${i}`,
      agent,
      agentIcon: "Bot",
      price: `${(Math.random() * 0.5 + 0.1).toFixed(3)} FLR`,
      reputation: Math.floor(Math.random() * 20) + 80,
      eta: `${Math.floor(Math.random() * 30) + 5}s`,
      timestamp: new Date(Date.now() - Math.random() * 60000),
    }));
  };

  // Order Book Row Component
  const OrderBookRow = ({ task, index }: { task: Task; index: number }) => {
    const config = getStatusConfig(task.status);
    const AgentIcon = getIcon(task.agentIcon);
    const isSelected = selectedTask?.id === task.id;
    const bids = generateBids(task);

    return (
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: index * 0.05 }}
        onClick={() => setSelectedTask(isSelected ? null : task)}
        className={`group relative overflow-hidden cursor-pointer transition-all duration-200 ${
          isSelected
            ? "bg-violet-500/10 border-l-2 border-l-violet-500"
            : "hover:bg-slate-800/30 border-l-2 border-l-transparent"
        }`}
      >
        <div className="grid grid-cols-12 gap-4 px-4 py-3 items-center">
          {/* Order ID & Type */}
          <div className="col-span-2">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${config.bg} ${config.color}`} />
              <span className="text-xs font-mono text-slate-500">{task.jobId.slice(0, 8)}...</span>
            </div>
            <span className={`text-[10px] font-medium ${config.color} mt-0.5 inline-block`}>
              {config.label}
            </span>
          </div>

          {/* Task Title */}
          <div className="col-span-3">
            <h4 className="text-sm font-medium text-slate-200 truncate group-hover:text-white transition-colors">
              {task.title}
            </h4>
            <div className="flex gap-1 mt-1">
              {task.tags.slice(0, 2).map((tag) => (
                <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-slate-800 text-slate-400 rounded">
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Agent / Bidders */}
          <div className="col-span-2">
            {task.status === "queued" ? (
              <div className="flex items-center gap-1">
                <div className="flex -space-x-2">
                  {bids.slice(0, 3).map((bid, i) => (
                    <div
                      key={bid.id}
                      className="w-6 h-6 rounded-full bg-slate-700 border-2 border-slate-900 flex items-center justify-center"
                    >
                      <Bot size={10} className="text-slate-400" />
                    </div>
                  ))}
                </div>
                <span className="text-xs text-slate-500 ml-1">{bids.length} bids</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-violet-500/20 flex items-center justify-center">
                  <AgentIcon size={12} className="text-violet-400" />
                </div>
                <span className="text-sm text-slate-300">{task.agent}</span>
              </div>
            )}
          </div>

          {/* Progress / Price */}
          <div className="col-span-2">
            {task.status === "executing" ? (
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-500">Progress</span>
                  <span className="text-amber-400 font-medium">{task.progress}%</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${task.progress}%` }}
                    className="h-full bg-gradient-to-r from-amber-500 to-orange-500 rounded-full"
                  />
                </div>
              </div>
            ) : task.status === "queued" ? (
              <div className="flex items-center gap-1">
                <DollarSign size={12} className="text-cyan-400" />
                <span className="text-sm font-medium text-cyan-400">
                  {bids.length > 0 ? bids[0].price : "0.15 FLR"}
                </span>
                <span className="text-[10px] text-slate-500">best</span>
              </div>
            ) : (
              <div className="flex items-center gap-1">
                {task.status === "completed" ? (
                  <TrendingUp size={14} className="text-emerald-400" />
                ) : (
                  <TrendingDown size={14} className="text-red-400" />
                )}
                <span className={`text-sm font-medium ${task.status === "completed" ? "text-emerald-400" : "text-red-400"}`}>
                  {task.status === "completed" ? "+100%" : "Failed"}
                </span>
              </div>
            )}
          </div>

          {/* ETA / Time */}
          <div className="col-span-2">
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Timer size={12} />
              <span>
                {task.status === "executing"
                  ? `~${Math.ceil((100 - task.progress) / 10)}s left`
                  : task.status === "queued"
                  ? "Awaiting bids"
                  : new Date(task.createdAt).toLocaleTimeString()}
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="col-span-1 flex justify-end">
            <button
              className={`p-1.5 rounded-lg transition-colors ${
                isSelected ? "bg-violet-500/20 text-violet-400" : "hover:bg-slate-700 text-slate-500"
              }`}
            >
              <ArrowUpRight size={14} />
            </button>
          </div>
        </div>

        {/* Animated border effect */}
        {task.status === "executing" && (
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-amber-500/50 to-transparent" />
          </div>
        )}
      </motion.div>
    );
  };

  // Stats Card Component
  const StatCard = ({ 
    label, 
    value, 
    change, 
    icon: Icon, 
    color 
  }: { 
    label: string; 
    value: string | number; 
    change?: string; 
    icon: LucideIcon; 
    color: string;
  }) => (
    <div className="bg-slate-900/40 backdrop-blur-sm rounded-xl border border-slate-800/50 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-slate-500 uppercase tracking-wide">{label}</span>
        <Icon size={16} className={color} />
      </div>
      <div className="flex items-end justify-between">
        <span className="text-2xl font-bold text-white">{value}</span>
        {change && (
          <span className={`text-xs font-medium flex items-center gap-0.5 ${
            change.startsWith("+") ? "text-emerald-400" : "text-red-400"
          }`}>
            {change.startsWith("+") ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
            {change}
          </span>
        )}
      </div>
    </div>
  );

  // Execution Feed Item
  const ExecutionFeedItem = ({ task, index }: { task: Task; index: number }) => {
    const config = getStatusConfig(task.status);
    
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.1 }}
        className="flex items-center gap-3 py-2 border-b border-slate-800/50 last:border-0"
      >
        <div className={`w-8 h-8 rounded-lg ${config.bg} flex items-center justify-center`}>
          {config.icon}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-slate-300 truncate">{task.title}</p>
          <p className="text-[10px] text-slate-500">{task.agent}</p>
        </div>
        <div className="text-right">
          <p className={`text-xs font-medium ${config.color}`}>{config.label}</p>
          <p className="text-[10px] text-slate-500">
            {new Date(task.createdAt).toLocaleTimeString()}
          </p>
        </div>
      </motion.div>
    );
  };

  // CSS Styles
  const pageStyles = `
    @keyframes grid-draw { 
      0% { stroke-dashoffset: 1000; opacity: 0; } 
      50% { opacity: 0.3; } 
      100% { stroke-dashoffset: 0; opacity: 0.15; } 
    }
    @keyframes pulse-glow { 
      0%, 100% { opacity: 0.1; transform: scale(1); } 
      50% { opacity: 0.3; transform: scale(1.1); } 
    }
    @keyframes ticker {
      0% { transform: translateX(0); }
      100% { transform: translateX(-50%); }
    }
    .grid-line { 
      stroke: #6366f1; 
      stroke-width: 0.5; 
      opacity: 0; 
      stroke-dasharray: 5 5; 
      stroke-dashoffset: 1000; 
      animation: grid-draw 2s ease-out forwards; 
    }
    .detail-dot { 
      fill: #a78bfa; 
      opacity: 0; 
      animation: pulse-glow 3s ease-in-out infinite; 
    }
    .ticker-scroll {
      animation: ticker 30s linear infinite;
    }
  `;

  if (loading) {
    return (
      <>
        <style>{pageStyles}</style>
        <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 flex items-center justify-center">
          <div className="text-center">
            <Loader2 size={32} className="text-violet-500 animate-spin mx-auto mb-4" />
            <p className="text-slate-400">Connecting to marketplace...</p>
          </div>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <style>{pageStyles}</style>
        <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 flex items-center justify-center">
          <div className="text-center">
            <XCircle size={32} className="text-red-500 mx-auto mb-4" />
            <p className="text-slate-300 font-medium">{error}</p>
            <button
              onClick={fetchTasks}
              className="mt-4 px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-500 transition-colors"
            >
              Retry Connection
            </button>
          </div>
        </div>
      </>
    );
  }

  const stats = data?.stats;
  const agents = data?.agents || [];
  const successRate = stats ? Math.round((stats.completed / Math.max(stats.total, 1)) * 100) : 0;

  return (
    <>
      <style>{pageStyles}</style>
      <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 text-slate-100 overflow-hidden relative">
        {/* Animated Background */}
        <FloatingPaths position={1} />
        <FloatingPaths position={-1} />
        
        {/* Grid Background */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="gridMarket" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(99, 102, 241, 0.04)" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#gridMarket)" />
        </svg>

        {/* Live Ticker Bar */}
        <div className="relative z-10 bg-slate-900/80 border-b border-slate-800/50 overflow-hidden">
          <div className="flex items-center h-8">
            <div className="flex-shrink-0 px-4 bg-violet-500/20 h-full flex items-center border-r border-slate-800/50">
              <Activity size={12} className="text-violet-400 mr-2 animate-pulse" />
              <span className="text-xs font-medium text-violet-300">LIVE</span>
            </div>
            <div className="flex-1 overflow-hidden">
              <div className="ticker-scroll flex items-center gap-8 px-4 whitespace-nowrap">
                {[...recentExecutions, ...recentExecutions].map((task, i) => (
                  <span key={`${task.id}-${i}`} className="text-xs text-slate-400 flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      task.status === "completed" ? "bg-emerald-400" : "bg-red-400"
                    }`} />
                    <span className="text-slate-500">{task.jobId.slice(0, 6)}</span>
                    <span>{task.title.slice(0, 30)}</span>
                    <span className={task.status === "completed" ? "text-emerald-400" : "text-red-400"}>
                      {task.status === "completed" ? "✓ Settled" : "✗ Failed"}
                    </span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Header */}
        <div className="relative z-10 max-w-7xl mx-auto px-6 pt-6">
          <div className="flex items-center justify-between mb-6">
            {/* Title */}
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
                  <Gavel size={24} className="text-white" />
                </div>
                <div className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 rounded-full border-2 border-slate-900 animate-pulse" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white flex items-center gap-2">
                  Order Book
                  <span className="text-xs font-normal px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded">LIVE</span>
                </h1>
                <p className="text-sm text-slate-500">Real-time AI agent task marketplace</p>
              </div>
            </div>

            {/* Search & Controls */}
            <div className="flex items-center gap-4">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search orders..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-64 pl-10 pr-4 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500/50 transition-all"
                />
              </div>
              
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>{agents.filter((a) => a.status === "active").length} agents online</span>
              </div>

              <button
                onClick={fetchTasks}
                className="p-2 hover:bg-slate-800 rounded-lg transition-colors group"
                title="Refresh"
              >
                <RefreshCw size={16} className="text-slate-400 group-hover:text-white transition-colors" />
              </button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <main className="relative z-10 max-w-7xl mx-auto px-6 pb-8">
          {/* Stats Row */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <StatCard
              label="Open Orders"
              value={stats?.queued || 0}
              icon={Gavel}
              color="text-cyan-400"
            />
            <StatCard
              label="Executing"
              value={stats?.executing || 0}
              icon={Activity}
              color="text-amber-400"
            />
            <StatCard
              label="Settled Today"
              value={stats?.completed || 0}
              change="+12%"
              icon={CheckCircle}
              color="text-emerald-400"
            />
            <StatCard
              label="Success Rate"
              value={`${successRate}%`}
              change={successRate >= 80 ? "+5%" : "-2%"}
              icon={BarChart3}
              color="text-violet-400"
            />
          </div>

          <div className="flex gap-6">
            {/* Order Book Panel */}
            <div className="flex-1">
              {/* Filter Tabs */}
              <div className="bg-slate-900/50 backdrop-blur-sm rounded-t-xl border border-slate-800/50 border-b-0 px-4 py-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1">
                    {[
                      { key: "all", label: "All Orders", count: stats?.total },
                      { key: "bids", label: "Open Bids", count: stats?.queued },
                      { key: "executing", label: "Executing", count: stats?.executing },
                      { key: "settled", label: "Settled", count: (stats?.completed || 0) + (stats?.failed || 0) },
                    ].map((tab) => (
                      <button
                        key={tab.key}
                        onClick={() => setActiveFilter(tab.key as typeof activeFilter)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                          activeFilter === tab.key
                            ? "bg-violet-500/20 text-violet-400"
                            : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                        }`}
                      >
                        <span>{tab.label}</span>
                        <span className={`px-1.5 py-0.5 rounded text-xs ${
                          activeFilter === tab.key
                            ? "bg-violet-500/30 text-violet-300"
                            : "bg-slate-800 text-slate-500"
                        }`}>
                          {tab.count || 0}
                        </span>
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center bg-slate-800/50 rounded-lg p-1">
                    <button
                      onClick={() => setViewMode("orderbook")}
                      className={`p-1.5 rounded transition-colors ${
                        viewMode === "orderbook" ? "bg-violet-500/20 text-violet-400" : "text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      <LayoutList size={16} />
                    </button>
                    <button
                      onClick={() => setViewMode("grid")}
                      className={`p-1.5 rounded transition-colors ${
                        viewMode === "grid" ? "bg-violet-500/20 text-violet-400" : "text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      <LayoutGrid size={16} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Order Book Table Header */}
              <div className="bg-slate-800/30 border-x border-slate-800/50 px-4 py-2">
                <div className="grid grid-cols-12 gap-4 text-xs text-slate-500 uppercase tracking-wide">
                  <div className="col-span-2">Order ID</div>
                  <div className="col-span-3">Task</div>
                  <div className="col-span-2">Agent / Bids</div>
                  <div className="col-span-2">Progress / Price</div>
                  <div className="col-span-2">Time</div>
                  <div className="col-span-1"></div>
                </div>
              </div>

              {/* Order Book Rows */}
              <div className="bg-slate-900/30 backdrop-blur-sm rounded-b-xl border border-slate-800/50 border-t-0 divide-y divide-slate-800/30 max-h-[500px] overflow-y-auto">
                <AnimatePresence mode="popLayout">
                  {filteredTasks.length > 0 ? (
                    filteredTasks.map((task, index) => (
                      <OrderBookRow key={task.id} task={task} index={index} />
                    ))
                  ) : (
                    <div className="py-12 text-center">
                      <div className="w-16 h-16 rounded-2xl bg-slate-800/50 flex items-center justify-center mx-auto mb-4">
                        <Gavel size={28} className="text-slate-600" />
                      </div>
                      <h3 className="text-lg font-medium text-slate-400 mb-2">No orders found</h3>
                      <p className="text-sm text-slate-500">Orders will appear here when tasks are created</p>
                    </div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Right Sidebar */}
            <div className="w-80 flex-shrink-0 space-y-4">
              {/* Selected Order Detail */}
              {selectedTask && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="bg-slate-900/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-4"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h4 className="text-sm font-semibold text-white">{selectedTask.title}</h4>
                      <p className="text-xs text-slate-500 font-mono mt-0.5">{selectedTask.jobId}</p>
                    </div>
                    <button
                      onClick={() => setSelectedTask(null)}
                      className="p-1 hover:bg-slate-800 rounded transition-colors"
                    >
                      <X size={14} className="text-slate-400" />
                    </button>
                  </div>

                  <div className="space-y-3">
                    {selectedTask.stages.map((stage, index) => {
                      const isComplete = stage.status === "complete";
                      const isInProgress = stage.status === "in_progress";

                      return (
                        <div key={stage.id} className="relative flex gap-3">
                          <div className="flex flex-col items-center">
                            <div
                              className={`w-2.5 h-2.5 rounded-full ${
                                isComplete
                                  ? "bg-emerald-500"
                                  : isInProgress
                                  ? "bg-amber-500 animate-pulse"
                                  : "bg-slate-700"
                              }`}
                            />
                            {index < selectedTask.stages.length - 1 && (
                              <div className={`w-0.5 flex-1 min-h-[30px] ${isComplete ? "bg-emerald-500/30" : "bg-slate-700/50"}`} />
                            )}
                          </div>
                          <div className="flex-1 pb-3">
                            <p className={`text-xs font-medium ${isComplete || isInProgress ? "text-slate-200" : "text-slate-500"}`}>
                              {stage.name}
                            </p>
                            <p className="text-[10px] text-slate-500 mt-0.5">{stage.description}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </motion.div>
              )}

              {/* Execution Feed */}
              <div className="bg-slate-900/50 backdrop-blur-sm rounded-xl border border-slate-800/50 p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Activity size={14} className="text-violet-400" />
                    Recent Executions
                  </h3>
                  <span className="text-[10px] text-slate-500">Auto-updating</span>
                </div>
                
                <div className="space-y-0 max-h-[300px] overflow-y-auto">
                  {recentExecutions.length > 0 ? (
                    recentExecutions.map((task, index) => (
                      <ExecutionFeedItem key={task.id} task={task} index={index} />
                    ))
                  ) : (
                    <p className="text-xs text-slate-500 text-center py-4">No recent executions</p>
                  )}
                </div>
              </div>

              {/* Active Agents */}
              <div className="bg-slate-900/50 backdrop-blur-sm rounded-xl border border-slate-800/50 p-4">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
                  <Shield size={14} className="text-emerald-400" />
                  Active Agents
                </h3>
                <div className="space-y-2">
                  {agents.filter(a => a.status === "active").slice(0, 5).map((agent) => {
                    const AgentIcon = getIcon(agent.icon);
                    return (
                      <div key={agent.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-800/30 transition-colors">
                        <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center">
                          <AgentIcon size={14} className="text-violet-400" />
                        </div>
                        <div className="flex-1">
                          <p className="text-xs font-medium text-slate-300">{agent.title}</p>
                          <div className="flex items-center gap-1 mt-0.5">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                            <span className="text-[10px] text-emerald-400">Ready</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </>
  );
}
