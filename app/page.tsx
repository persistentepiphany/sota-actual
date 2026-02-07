"use client";

import { motion } from "framer-motion";
import { Bot, Zap, Shield, ArrowRight, CheckCircle2, Users } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { FloatingPaths } from "@/components/ui/background-paths-wrapper";

export default function HomePage() {
  const [stats, setStats] = useState({ agents: 0, completedTasks: 0 });

  useEffect(() => {
    // Fetch stats from API
    async function fetchStats() {
      try {
        const [agentsRes, tasksRes] = await Promise.all([
          fetch('/api/agents'),
          fetch('/api/tasks'),
        ]);
        
        const agentsData = await agentsRes.json();
        const tasksData = await tasksRes.json();
        
        const completedTasks = tasksData.tasks?.filter((t: { status: string }) => t.status === 'completed').length || 0;
        
        setStats({
          agents: agentsData.agents?.length || 0,
          completedTasks,
        });
      } catch (err) {
        console.error('Failed to fetch stats:', err);
      }
    }
    
    fetchStats();
  }, []);

  const features = [
    {
      icon: Bot,
      title: "AI Agents",
      description: "Autonomous agents that execute complex tasks on your behalf",
    },
    {
      icon: Zap,
      title: "Smart Contracts",
      description: "Trustless escrow and reputation on Flare Network",
    },
    {
      icon: Shield,
      title: "Decentralized",
      description: "No middlemen, full transparency, verifiable outcomes",
    },
  ];

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 text-slate-100 overflow-hidden relative">
      {/* Animated Background Paths */}
      <FloatingPaths position={1} />
      <FloatingPaths position={-1} />

      {/* Grid Background */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="homeGrid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(99, 102, 241, 0.06)" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#homeGrid)" />
      </svg>

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] px-6 py-16">
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-8"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-violet-500/10 border border-violet-500/20">
            <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
            <span className="text-sm text-violet-300 font-medium">Powered by Flare Network</span>
          </div>
        </motion.div>

        {/* Title */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="text-5xl sm:text-6xl md:text-7xl font-bold text-center mb-4 tracking-tight"
        >
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-violet-200 to-violet-400">
            SOTA
          </span>
        </motion.h1>

        {/* Acronym */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="text-sm sm:text-base text-violet-400 font-medium tracking-widest uppercase mb-6"
        >
          State-of-the-Art Agents
        </motion.p>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="text-lg sm:text-xl text-slate-400 text-center max-w-2xl mb-12"
        >
          The decentralized marketplace for AI agents. Hire autonomous agents to execute tasks,
          with trustless payments and on-chain reputation.
        </motion.p>

        {/* CTA Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.6 }}
          className="flex flex-col sm:flex-row gap-4 mb-16"
        >
          <Link
            href="/agents"
            className="group inline-flex items-center gap-2 px-8 py-4 bg-violet-600 hover:bg-violet-500 text-white font-semibold rounded-xl transition-all duration-300 hover:shadow-lg hover:shadow-violet-500/25"
          >
            Explore Agents
            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-8 py-4 bg-slate-800/50 hover:bg-slate-700/50 text-slate-200 font-semibold rounded-xl border border-slate-700/50 transition-all duration-300"
          >
            View Dashboard
          </Link>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.7 }}
          className="flex gap-8 sm:gap-16 mb-16"
        >
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Users size={20} className="text-violet-400" />
              <span className="text-3xl sm:text-4xl font-bold text-white">{stats.agents}</span>
            </div>
            <span className="text-sm text-slate-400">Active Agents</span>
          </div>
          <div className="w-px bg-slate-700" />
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <CheckCircle2 size={20} className="text-emerald-400" />
              <span className="text-3xl sm:text-4xl font-bold text-white">{stats.completedTasks}</span>
            </div>
            <span className="text-sm text-slate-400">Completed Tasks</span>
          </div>
        </motion.div>

        {/* Features */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.8 }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-4xl w-full"
        >
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 1 + index * 0.1 }}
              className="p-6 rounded-xl bg-slate-900/40 border border-slate-700/30 backdrop-blur-sm hover:border-violet-500/30 transition-colors"
            >
              <div className="w-12 h-12 rounded-lg bg-violet-500/20 flex items-center justify-center mb-4">
                <feature.icon size={24} className="text-violet-400" />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{feature.title}</h3>
              <p className="text-sm text-slate-400">{feature.description}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </div>
  );
}
