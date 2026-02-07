"use client";
import React, { useState, useEffect } from "react";
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
  type LucideIcon,
} from "lucide-react";
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

interface DashboardData {
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

export default function TasksDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [activeTab, setActiveTab] = useState<"current" | "complete" | "unsuccessful">("current");

  // Fetch tasks from API
  const fetchTasks = async () => {
    try {
      const res = await fetch("/api/tasks");
      if (!res.ok) throw new Error("Failed to fetch tasks");
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err) {
      console.error("Error fetching tasks:", err);
      setError("Failed to load tasks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 10000);
    return () => clearInterval(interval);
  }, []);

  // Filter tasks by search query
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

  // Get tasks for the active tab
  const getTabTasks = () => {
    if (!data?.grouped) return [];
    switch (activeTab) {
      case "current":
        return [...(data.grouped.executing || []), ...(data.grouped.queued || [])];
      case "complete":
        return data.grouped.completed || [];
      case "unsuccessful":
        return data.grouped.failed || [];
      default:
        return [];
    }
  };

  const tabTasks = filterTasks(getTabTasks());

  const getIcon = (iconName: string): LucideIcon => iconMap[iconName] || Bot;

  const getStatusColor = (status: string) => {
    switch (status) {
      case "executing":
        return "text-amber-400 bg-amber-400/10 border-amber-400/30";
      case "queued":
        return "text-indigo-400 bg-indigo-400/10 border-indigo-400/30";
      case "completed":
        return "text-emerald-400 bg-emerald-400/10 border-emerald-400/30";
      case "failed":
        return "text-red-400 bg-red-400/10 border-red-400/30";
      default:
        return "text-slate-400 bg-slate-400/10 border-slate-400/30";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "executing":
        return <Clock size={12} className="animate-pulse" />;
      case "queued":
        return <Loader2 size={12} className="animate-spin" />;
      case "completed":
        return <CheckCircle size={12} />;
      case "failed":
        return <XCircle size={12} />;
      default:
        return null;
    }
  };

  const TaskCard = ({ task }: { task: Task }) => {
    const AgentIcon = getIcon(task.agentIcon);
    const isSelected = selectedTask?.id === task.id;

    return (
      <div
        onClick={() => setSelectedTask(isSelected ? null : task)}
        className={`group bg-slate-900/50 backdrop-blur-sm rounded-xl border p-4 cursor-pointer transition-all hover:bg-slate-800/50 ${
          isSelected
            ? "border-violet-500/50 ring-2 ring-violet-500/20"
            : "border-slate-700/50 hover:border-slate-600/50"
        }`}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-medium text-slate-200 truncate group-hover:text-white transition-colors">
              {task.title}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5 font-mono">{task.jobId}</p>
          </div>
          <span
            className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(
              task.status
            )}`}
          >
            {getStatusIcon(task.status)}
            <span className="capitalize">{task.status}</span>
          </span>
        </div>

        {/* Description */}
        <p className="text-sm text-slate-400 line-clamp-2 mb-3">{task.description}</p>

        {/* Progress Bar (for executing tasks) */}
        {task.status === "executing" && (
          <div className="mb-3">
            <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
              <span>Progress</span>
              <span className="text-violet-400">{task.progress}%</span>
            </div>
            <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-all duration-500"
                style={{ width: `${task.progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Executor (Agent) */}
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-violet-500/20 flex items-center justify-center">
              <AgentIcon size={14} className="text-violet-400" />
            </div>
            <span className="text-slate-300 font-medium">{task.agent}</span>
          </div>
          {task.tags.length > 0 && (
            <span className="px-2 py-0.5 bg-slate-800 text-slate-400 rounded text-xs">
              {task.tags[0]}
            </span>
          )}
        </div>
      </div>
    );
  };

  // Styles matching orbital landing
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
  `;

  if (loading) {
    return (
      <>
        <style>{pageStyles}</style>
        <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 flex items-center justify-center">
          <div className="text-center">
            <Loader2 size={32} className="text-violet-500 animate-spin mx-auto mb-4" />
            <p className="text-slate-400">Loading tasks...</p>
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
              Retry
            </button>
          </div>
        </div>
      </>
    );
  }

  const stats = data?.stats;
  const grouped = data?.grouped;
  const agents = data?.agents || [];

  return (
    <>
      <style>{pageStyles}</style>
      <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 text-slate-100 overflow-hidden relative">
        {/* Animated Background Paths */}
        <FloatingPaths position={1} />
        <FloatingPaths position={-1} />
        
        {/* Grid SVG Background */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            <pattern id="gridDashboard" width="60" height="60" patternUnits="userSpaceOnUse">
              <path
                d="M 60 0 L 0 0 0 60"
                fill="none"
                stroke="rgba(99, 102, 241, 0.06)"
                strokeWidth="0.5"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#gridDashboard)" />
          <line x1="0" y1="15%" x2="100%" y2="15%" className="grid-line" style={{ animationDelay: "0.5s" }} />
          <line x1="0" y1="85%" x2="100%" y2="85%" className="grid-line" style={{ animationDelay: "1s" }} />
          <circle cx="10%" cy="15%" r="2" className="detail-dot" style={{ animationDelay: "1.5s" }} />
          <circle cx="90%" cy="15%" r="2" className="detail-dot" style={{ animationDelay: "1.7s" }} />
          <circle cx="10%" cy="85%" r="2" className="detail-dot" style={{ animationDelay: "1.9s" }} />
          <circle cx="90%" cy="85%" r="2" className="detail-dot" style={{ animationDelay: "2.1s" }} />
        </svg>

        {/* Search Bar */}
        <div className="relative z-10 max-w-7xl mx-auto px-6 pt-6">
          <div className="flex items-center justify-between mb-6">
            {/* Title */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-violet-500/20 flex items-center justify-center">
                <Zap size={20} className="text-violet-400" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-white">Task Dashboard</h1>
                <p className="text-xs text-slate-500">Agent orchestration center</p>
              </div>
            </div>

            {/* Search */}
            <div className="flex-1 max-w-md mx-8">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search tasks, agents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500/50 focus:bg-slate-900 transition-all"
                />
              </div>
            </div>

            {/* Status */}
            <div className="flex items-center gap-4 text-xs text-slate-400">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>{agents.filter((a) => a.status === "active").length} agents online</span>
              </div>
              <button
                onClick={fetchTasks}
                className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
                title="Refresh"
              >
                <RefreshCw size={16} className="text-slate-400 hover:text-white" />
              </button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <main className="relative z-10 max-w-7xl mx-auto px-6 py-6">
          {/* Tabs */}
          <div className="bg-slate-900/30 backdrop-blur-sm rounded-xl border border-slate-800/50 p-1.5 mb-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setActiveTab("current")}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    activeTab === "current"
                      ? "bg-violet-500/20 text-violet-400 shadow-lg shadow-violet-500/10"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                  }`}
                >
                  <Zap size={16} />
                  <span>Current</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    activeTab === "current" ? "bg-violet-500/30 text-violet-300" : "bg-slate-700/50 text-slate-500"
                  }`}>
                    {(stats?.executing || 0) + (stats?.queued || 0)}
                  </span>
                </button>
                <button
                  onClick={() => setActiveTab("complete")}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    activeTab === "complete"
                      ? "bg-emerald-500/20 text-emerald-400 shadow-lg shadow-emerald-500/10"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                  }`}
                >
                  <CheckCircle size={16} />
                  <span>Complete</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    activeTab === "complete" ? "bg-emerald-500/30 text-emerald-300" : "bg-slate-700/50 text-slate-500"
                  }`}>
                    {stats?.completed || 0}
                  </span>
                </button>
                <button
                  onClick={() => setActiveTab("unsuccessful")}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    activeTab === "unsuccessful"
                      ? "bg-red-500/20 text-red-400 shadow-lg shadow-red-500/10"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                  }`}
                >
                  <XCircle size={16} />
                  <span>Unsuccessful</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    activeTab === "unsuccessful" ? "bg-red-500/30 text-red-300" : "bg-slate-700/50 text-slate-500"
                  }`}>
                    {stats?.failed || 0}
                  </span>
                </button>
              </div>

              {/* View Controls */}
              <div className="flex items-center gap-2 pr-2">
                <div className="flex items-center bg-slate-800/50 rounded-lg p-1">
                  <button
                    onClick={() => setViewMode("list")}
                    className={`p-1.5 rounded transition-colors ${
                      viewMode === "list" ? "bg-violet-500/20 text-violet-400" : "text-slate-500 hover:text-slate-300"
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
          </div>

          {/* Task List */}
          <div className="flex gap-6">
            <div className="flex-1">
              {tabTasks.length > 0 ? (
                <div
                  className={
                    viewMode === "grid"
                      ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
                      : "space-y-3"
                  }
                >
                  {tabTasks.map((task) => (
                    <TaskCard key={task.id} task={task} />
                  ))}
                </div>
              ) : (
                /* Empty State */
                <div className="bg-slate-900/30 backdrop-blur-sm rounded-xl border-2 border-dashed border-slate-700/50 p-12 text-center">
                  <div className="w-16 h-16 rounded-2xl bg-violet-500/10 flex items-center justify-center mx-auto mb-4">
                    <Bot size={28} className="text-violet-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">No tasks yet</h3>
                  <p className="text-slate-400 mb-6">Create your first task to get started with AI agents</p>
                </div>
              )}
            </div>

            {/* Selected Task Detail Panel */}
            {selectedTask && (
              <div className="w-96 flex-shrink-0">
                <div className="bg-slate-900/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-5 sticky top-24">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-1">
                    <div>
                      <h4 className="text-base font-semibold text-white">{selectedTask.title}</h4>
                      <p className="text-xs text-slate-500 font-mono">Task #{selectedTask.jobId}</p>
                    </div>
                    <button
                      onClick={() => setSelectedTask(null)}
                      className="p-1 hover:bg-slate-800 rounded transition-colors"
                    >
                      <X size={16} className="text-slate-400" />
                    </button>
                  </div>

                  {/* Stages Timeline */}
                  <div className="mt-6 space-y-0">
                    {selectedTask.stages.map((stage, index) => {
                      const isLast = index === selectedTask.stages.length - 1;
                      const isComplete = stage.status === "complete";
                      const isInProgress = stage.status === "in_progress";
                      const isPending = stage.status === "pending";

                      return (
                        <div key={stage.id} className="relative flex gap-4">
                          {/* Timeline Line & Dot */}
                          <div className="flex flex-col items-center">
                            <div
                              className={`w-3 h-3 rounded-full border-2 z-10 ${
                                isComplete
                                  ? "bg-blue-500 border-blue-500"
                                  : isInProgress
                                  ? "bg-blue-500 border-blue-500 animate-pulse"
                                  : "bg-slate-800 border-slate-600"
                              }`}
                            />
                            {!isLast && (
                              <div
                                className={`w-0.5 flex-1 min-h-[60px] ${
                                  isComplete ? "bg-blue-500/50" : "bg-slate-700"
                                }`}
                              />
                            )}
                          </div>

                          {/* Stage Card */}
                          <div
                            className={`flex-1 mb-4 p-4 rounded-xl border transition-all ${
                              isInProgress
                                ? "bg-blue-500/5 border-blue-500/30"
                                : "bg-slate-800/30 border-slate-700/50"
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <h5 className={`text-sm font-medium ${
                                isPending ? "text-slate-400" : "text-white"
                              }`}>
                                {stage.name}
                              </h5>
                              <span
                                className={`text-xs font-medium ${
                                  isComplete
                                    ? "text-emerald-400"
                                    : isInProgress
                                    ? "text-blue-400"
                                    : "text-slate-500"
                                }`}
                              >
                                {isComplete && "✓ Complete"}
                                {isInProgress && "In Progress"}
                                {isPending && "Pending"}
                              </span>
                            </div>
                            <p className={`text-sm leading-relaxed ${
                              isInProgress ? "text-blue-300/80" : isPending ? "text-slate-500" : "text-slate-400"
                            }`}>
                              {stage.description}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </>
  );
}
