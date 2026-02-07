"use client";

import React, { useState } from "react";
import { type LucideIcon, ChevronRight, CheckCircle, Clock, Circle } from "lucide-react";
import { FloatingPaths } from './background-paths-wrapper';

interface TimelineItem {
  id: number;
  title: string;
  date: string;
  content: string;
  category: string;
  icon: LucideIcon;
  relatedIds: number[];
  status: "completed" | "in-progress" | "pending";
  energy: number;
}

interface ProjectTimelineProps {
  timelineData: TimelineItem[];
  centerLabel: string;
}

export default function ProjectTimeline({ timelineData, centerLabel }: ProjectTimelineProps) {
  const [selectedItem, setSelectedItem] = useState<TimelineItem | null>(null);
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "text-emerald-400 bg-emerald-500/20 border-emerald-500/30";
      case "in-progress":
        return "text-violet-400 bg-violet-500/20 border-violet-500/30";
      default:
        return "text-slate-400 bg-slate-700/30 border-slate-600/30";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle size={14} className="text-emerald-400" />;
      case "in-progress":
        return <Clock size={14} className="text-violet-400" />;
      default:
        return <Circle size={14} className="text-slate-500" />;
    }
  };

  const pageStyles = `
    @keyframes pulse-glow {
      0%, 100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); }
      50% { box-shadow: 0 0 40px rgba(139, 92, 246, 0.5); }
    }
    
    @keyframes float {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-5px); }
    }
    
    .timeline-card {
      transition: all 0.3s ease;
    }
    
    .timeline-card:hover {
      transform: translateX(8px);
    }
    
    .energy-bar {
      transition: width 0.5s ease;
    }
  `;

  return (
    <>
      <style>{pageStyles}</style>
      <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 text-slate-100 overflow-hidden relative">
        {/* Animated Background Paths */}
        <FloatingPaths position={1} />
        <FloatingPaths position={-1} />
        
        {/* Grid Background */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="roadmapGrid" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(99, 102, 241, 0.08)" strokeWidth="0.5"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#roadmapGrid)" />
        </svg>

        <div className="relative z-10 max-w-6xl mx-auto px-6 py-12">
          {/* Header */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-violet-500/10 border border-violet-500/20 mb-6">
              <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
              <span className="text-sm text-violet-300 font-medium">{centerLabel} Roadmap</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Project Timeline
            </h1>
            <p className="text-slate-400 max-w-xl mx-auto">
              Track our journey from concept to launch. Each milestone brings us closer to revolutionizing the AI agent marketplace.
            </p>
          </div>

          {/* Timeline */}
          <div className="relative">
            {/* Vertical Line */}
            <div className="absolute left-8 top-0 bottom-0 w-px bg-gradient-to-b from-violet-500/50 via-violet-500/20 to-transparent" />

            <div className="space-y-6">
              {timelineData.map((item, index) => {
                const Icon = item.icon;
                const isSelected = selectedItem?.id === item.id;
                const isHovered = hoveredId === item.id;
                const isRelated = selectedItem?.relatedIds.includes(item.id);

                return (
                  <div
                    key={item.id}
                    className={`relative pl-20 timeline-card ${isRelated ? "opacity-100" : selectedItem ? "opacity-50" : "opacity-100"}`}
                    onMouseEnter={() => setHoveredId(item.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    onClick={() => setSelectedItem(isSelected ? null : item)}
                  >
                    {/* Node */}
                    <div
                      className={`absolute left-5 top-4 w-6 h-6 rounded-full flex items-center justify-center border-2 transition-all cursor-pointer ${
                        isSelected || isHovered
                          ? "bg-violet-500 border-violet-400 scale-125"
                          : item.status === "completed"
                          ? "bg-emerald-500/20 border-emerald-500/50"
                          : item.status === "in-progress"
                          ? "bg-violet-500/20 border-violet-500/50"
                          : "bg-slate-800 border-slate-600"
                      }`}
                    >
                      <div className={`w-2 h-2 rounded-full ${
                        item.status === "completed" ? "bg-emerald-400" :
                        item.status === "in-progress" ? "bg-violet-400 animate-pulse" :
                        "bg-slate-500"
                      }`} />
                    </div>

                    {/* Card */}
                    <div
                      className={`p-5 rounded-xl border backdrop-blur-sm cursor-pointer transition-all ${
                        isSelected
                          ? "bg-violet-500/10 border-violet-500/40"
                          : isHovered
                          ? "bg-slate-800/60 border-slate-600/60"
                          : "bg-slate-900/40 border-slate-700/30"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-4 flex-1">
                          {/* Icon */}
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${getStatusColor(item.status)}`}>
                            <Icon size={20} />
                          </div>

                          {/* Content */}
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <h3 className="font-semibold text-white">{item.title}</h3>
                              <span className={`px-2 py-0.5 text-xs rounded-full border ${getStatusColor(item.status)}`}>
                                {item.category}
                              </span>
                              {getStatusIcon(item.status)}
                            </div>
                            <p className="text-sm text-slate-400 mb-3">{item.content}</p>

                            {/* Energy Bar */}
                            <div className="flex items-center gap-3">
                              <span className="text-xs text-slate-500">{item.date}</span>
                              <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div
                                  className={`h-full energy-bar rounded-full ${
                                    item.status === "completed"
                                      ? "bg-emerald-500"
                                      : item.status === "in-progress"
                                      ? "bg-violet-500"
                                      : "bg-slate-600"
                                  }`}
                                  style={{ width: `${item.energy}%` }}
                                />
                              </div>
                              <span className="text-xs text-slate-500">{item.energy}%</span>
                            </div>
                          </div>
                        </div>

                        {/* Arrow */}
                        <ChevronRight
                          size={20}
                          className={`text-slate-500 transition-transform ${isSelected ? "rotate-90" : ""}`}
                        />
                      </div>

                      {/* Expanded Content */}
                      {isSelected && (
                        <div className="mt-4 pt-4 border-t border-slate-700/50">
                          <div className="flex items-center gap-2 text-sm text-slate-400">
                            <span className="text-violet-400">Related milestones:</span>
                            {item.relatedIds.map((relId) => {
                              const related = timelineData.find((t) => t.id === relId);
                              return related ? (
                                <span
                                  key={relId}
                                  className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-xs cursor-pointer hover:bg-slate-700"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedItem(related);
                                  }}
                                >
                                  {related.title}
                                </span>
                              ) : null;
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Stats */}
          <div className="mt-12 grid grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-700/30 text-center">
              <div className="text-2xl font-bold text-emerald-400">
                {timelineData.filter((t) => t.status === "completed").length}
              </div>
              <div className="text-xs text-slate-500 mt-1">Completed</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-700/30 text-center">
              <div className="text-2xl font-bold text-violet-400">
                {timelineData.filter((t) => t.status === "in-progress").length}
              </div>
              <div className="text-xs text-slate-500 mt-1">In Progress</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-700/30 text-center">
              <div className="text-2xl font-bold text-slate-400">
                {timelineData.filter((t) => t.status === "pending").length}
              </div>
              <div className="text-xs text-slate-500 mt-1">Upcoming</div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
