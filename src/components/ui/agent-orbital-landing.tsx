"use client";
import React, { useState, useEffect, useRef } from 'react';
import { Bot, Phone, Calendar, Briefcase, X, Zap, Star, Activity, Loader2, Search, type LucideIcon } from 'lucide-react';
import { FloatingPaths } from './background-paths-wrapper';

// Icon mapping for dynamic icons from DB
const iconMap: Record<string, LucideIcon> = {
  Bot,
  Phone,
  Calendar,
  Briefcase,
};

interface Agent {
  id: number;
  title: string;
  description: string;
  icon: string;
  status: "online" | "busy" | "offline";
  totalRequests: number;
  reputation: number;
  successRate: number;
}

interface ButlerData {
  title: string;
  description: string;
  icon: string;
  status: "online" | "busy" | "offline";
  totalRequests: number;
  reputation: number;
  successRate: number;
}

const AgentOrbitalLanding = () => {
  const [mouseGradientStyle, setMouseGradientStyle] = useState({
    left: '0px',
    top: '0px',
    opacity: 0,
  });
  const [ripples, setRipples] = useState<Array<{ id: number; x: number; y: number }>>([]);
  const [scrolled, setScrolled] = useState(false);
  const [rotationAngle, setRotationAngle] = useState(0);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [showButler, setShowButler] = useState(false);
  const floatingElementsRef = useRef<Element[]>([]);
  
  // Data from API
  const [agents, setAgents] = useState<Agent[]>([]);
  const [allAgents, setAllAgents] = useState<Agent[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [butler, setButler] = useState<ButlerData>({
    title: "Butler",
    description: "Your AI concierge orchestrating all agents",
    icon: "Bot",
    status: "online",
    totalRequests: 0,
    reputation: 5.0,
    successRate: 100,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch agents from API
  useEffect(() => {
    const fetchAgents = async () => {
      try {
        // Fetch both dashboard agents and all agents
        const [dashboardRes, allAgentsRes] = await Promise.all([
          fetch('/api/agents/dashboard'),
          fetch('/api/agents')
        ]);
        
        if (!dashboardRes.ok) throw new Error('Failed to fetch agents');
        const dashboardData = await dashboardRes.json();
        
        setAgents(dashboardData.agents || []);
        if (dashboardData.butler) {
          setButler(dashboardData.butler);
        }
        
        // Set all agents for the list
        if (allAgentsRes.ok) {
          const allData = await allAgentsRes.json();
          setAllAgents((allData.agents || []).map((a: Record<string, unknown>) => ({
            id: a.id as number,
            title: a.title as string,
            description: a.description as string,
            icon: (a.icon as string) || 'Bot',
            status: (a.status === 'active' ? 'online' : a.status === 'busy' ? 'busy' : 'offline') as "online" | "busy" | "offline",
            totalRequests: (a.totalRequests as number) || 0,
            reputation: (a.reputation as number) || 5.0,
            successRate: a.totalRequests ? Math.round(((a.successfulRequests as number) / (a.totalRequests as number)) * 100) : 100,
          })));
        }
        
        setError(null);
      } catch (err) {
        console.error('Error fetching agents:', err);
        setError('Failed to load agents');
        // Fallback to default data
        setAgents([
          { id: 1, title: "Caller", description: "Phone verification via Twilio", icon: "Phone", status: "online", totalRequests: 0, reputation: 5.0, successRate: 100 },
          { id: 2, title: "Hackathon", description: "Event discovery & registration", icon: "Calendar", status: "online", totalRequests: 0, reputation: 5.0, successRate: 100 },
        ]);
      } finally {
        setLoading(false);
      }
    };
    
    fetchAgents();
    // Refresh every 30 seconds
    const interval = setInterval(fetchAgents, 30000);
    return () => clearInterval(interval);
  }, []);

  // Filter agents by search query
  const filteredAgents = allAgents.filter(agent => 
    agent.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    agent.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Helper to get icon component from string
  const getIcon = (iconName: string): LucideIcon => {
    return iconMap[iconName] || Bot;
  };

  // Word animation
  useEffect(() => {
    const animateWords = () => {
      const wordElements = document.querySelectorAll('.word-animate');
      wordElements.forEach(word => {
        const delay = parseInt(word.getAttribute('data-delay') || '0');
        setTimeout(() => {
          if (word) (word as HTMLElement).style.animation = 'word-appear 0.8s ease-out forwards';
        }, delay);
      });
    };
    const timeoutId = setTimeout(animateWords, 500);
    return () => clearTimeout(timeoutId);
  }, []);

  // Mouse gradient follow
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMouseGradientStyle({
        left: `${e.clientX}px`,
        top: `${e.clientY}px`,
        opacity: 1,
      });
    };
    const handleMouseLeave = () => {
      setMouseGradientStyle(prev => ({ ...prev, opacity: 0 }));
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseleave', handleMouseLeave);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  // Click ripple effect
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const newRipple = { id: Date.now(), x: e.clientX, y: e.clientY };
      setRipples(prev => [...prev, newRipple]);
      setTimeout(() => setRipples(prev => prev.filter(r => r.id !== newRipple.id)), 1000);
    };
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, []);

  // Word hover effects
  useEffect(() => {
    const wordElements = document.querySelectorAll('.word-animate');
    const handleMouseEnter = (e: Event) => { 
      if (e.target) (e.target as HTMLElement).style.textShadow = '0 0 20px rgba(203, 213, 225, 0.5)'; 
    };
    const handleMouseLeave = (e: Event) => { 
      if (e.target) (e.target as HTMLElement).style.textShadow = 'none'; 
    };
    wordElements.forEach(word => {
      word.addEventListener('mouseenter', handleMouseEnter);
      word.addEventListener('mouseleave', handleMouseLeave);
    });
    return () => {
      wordElements.forEach(word => {
        if (word) {
          word.removeEventListener('mouseenter', handleMouseEnter);
          word.removeEventListener('mouseleave', handleMouseLeave);
        }
      });
    };
  }, []);

  // Floating elements on scroll
  useEffect(() => {
    const elements = document.querySelectorAll('.floating-element-animate');
    floatingElementsRef.current = Array.from(elements);
    const handleScroll = () => {
      if (!scrolled) {
        setScrolled(true);
        floatingElementsRef.current.forEach((el, index) => {
          setTimeout(() => {
            if (el) {
              (el as HTMLElement).style.animationPlayState = 'running';
              (el as HTMLElement).style.opacity = '';
            }
          }, (parseFloat((el as HTMLElement).style.animationDelay || "0") * 1000) + index * 100);
        });
      }
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [scrolled]);

  // Orbital rotation
  useEffect(() => {
    const interval = setInterval(() => {
      setRotationAngle(prev => (prev + 0.3) % 360);
    }, 50);
    return () => clearInterval(interval);
  }, []);

  // Calculate agent position on orbit
  const getAgentPosition = (index: number, total: number) => {
    const angle = ((index / total) * 360 + rotationAngle) % 360;
    const radius = 160;
    const radian = (angle * Math.PI) / 180;
    const x = radius * Math.cos(radian);
    const y = radius * Math.sin(radian);
    const opacity = 0.5 + 0.5 * ((1 + Math.sin(radian)) / 2);
    const scale = 0.8 + 0.2 * ((1 + Math.sin(radian)) / 2);
    return { x, y, opacity, scale };
  };

  const pageStyles = `
    #mouse-gradient-react {
      position: fixed;
      pointer-events: none;
      border-radius: 9999px;
      background-image: radial-gradient(circle, rgba(139, 92, 246, 0.08), rgba(59, 130, 246, 0.05), transparent 70%);
      transform: translate(-50%, -50%);
      will-change: left, top, opacity;
      transition: left 70ms linear, top 70ms linear, opacity 300ms ease-out;
    }
    @keyframes word-appear { 
      0% { opacity: 0; transform: translateY(30px) scale(0.8); filter: blur(10px); } 
      50% { opacity: 0.8; transform: translateY(10px) scale(0.95); filter: blur(2px); } 
      100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); } 
    }
    @keyframes grid-draw { 
      0% { stroke-dashoffset: 1000; opacity: 0; } 
      50% { opacity: 0.3; } 
      100% { stroke-dashoffset: 0; opacity: 0.15; } 
    }
    @keyframes pulse-glow { 
      0%, 100% { opacity: 0.1; transform: scale(1); } 
      50% { opacity: 0.3; transform: scale(1.1); } 
    }
    @keyframes orbit-pulse {
      0%, 100% { opacity: 0.2; }
      50% { opacity: 0.4; }
    }
    .word-animate { 
      display: inline-block; 
      opacity: 0; 
      margin: 0 0.15em; 
      transition: color 0.3s ease, transform 0.3s ease; 
    }
    .word-animate:hover { 
      color: #c4b5fd; 
      transform: translateY(-2px); 
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
    .corner-element-animate { 
      position: absolute; 
      width: 40px; 
      height: 40px; 
      border: 1px solid rgba(139, 92, 246, 0.2); 
      opacity: 0; 
      animation: word-appear 1s ease-out forwards; 
    }
    .text-decoration-animate { position: relative; }
    .text-decoration-animate::after { 
      content: ''; 
      position: absolute; 
      bottom: -4px; 
      left: 0; 
      width: 0; 
      height: 1px; 
      background: linear-gradient(90deg, transparent, #a78bfa, transparent); 
      animation: underline-grow 2s ease-out forwards; 
      animation-delay: 2s; 
    }
    @keyframes underline-grow { to { width: 100%; } }
    .floating-element-animate { 
      position: absolute; 
      width: 2px; 
      height: 2px; 
      background: #a78bfa; 
      border-radius: 50%; 
      opacity: 0; 
      animation: float 4s ease-in-out infinite; 
      animation-play-state: paused; 
    }
    @keyframes float { 
      0%, 100% { transform: translateY(0) translateX(0); opacity: 0.2; } 
      25% { transform: translateY(-10px) translateX(5px); opacity: 0.6; } 
      50% { transform: translateY(-5px) translateX(-3px); opacity: 0.4; } 
      75% { transform: translateY(-15px) translateX(7px); opacity: 0.8; } 
    }
    .ripple-effect { 
      position: fixed; 
      width: 4px; 
      height: 4px; 
      background: rgba(167, 139, 250, 0.6); 
      border-radius: 50%; 
      transform: translate(-50%, -50%); 
      pointer-events: none; 
      animation: pulse-glow 1s ease-out forwards; 
      z-index: 9999; 
    }
    .orbit-ring {
      animation: orbit-pulse 3s ease-in-out infinite;
    }
  `;

  return (
    <>
      <style>{pageStyles}</style>
      <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 text-slate-100 overflow-hidden relative">
        
        {/* Animated Background Paths */}
        <FloatingPaths position={1} />
        <FloatingPaths position={-1} />
        
        {/* Grid SVG Background */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <pattern id="gridReactDarkResponsive" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(99, 102, 241, 0.06)" strokeWidth="0.5"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#gridReactDarkResponsive)" />
          <line x1="0" y1="20%" x2="100%" y2="20%" className="grid-line" style={{ animationDelay: '0.5s' }} />
          <line x1="0" y1="80%" x2="100%" y2="80%" className="grid-line" style={{ animationDelay: '1s' }} />
          <line x1="20%" y1="0" x2="20%" y2="100%" className="grid-line" style={{ animationDelay: '1.5s' }} />
          <line x1="80%" y1="0" x2="80%" y2="100%" className="grid-line" style={{ animationDelay: '2s' }} />
          <line x1="50%" y1="0" x2="50%" y2="100%" className="grid-line" style={{ animationDelay: '2.5s', opacity: '0.05' }} />
          <line x1="0" y1="50%" x2="100%" y2="50%" className="grid-line" style={{ animationDelay: '3s', opacity: '0.05' }} />
          <circle cx="20%" cy="20%" r="2" className="detail-dot" style={{ animationDelay: '3s' }} />
          <circle cx="80%" cy="20%" r="2" className="detail-dot" style={{ animationDelay: '3.2s' }} />
          <circle cx="20%" cy="80%" r="2" className="detail-dot" style={{ animationDelay: '3.4s' }} />
          <circle cx="80%" cy="80%" r="2" className="detail-dot" style={{ animationDelay: '3.6s' }} />
          <circle cx="50%" cy="50%" r="1.5" className="detail-dot" style={{ animationDelay: '4s' }} />
        </svg>

        {/* Corner Elements */}
        <div className="corner-element-animate top-4 left-4 sm:top-6 sm:left-6 md:top-8 md:left-8" style={{ animationDelay: '4s' }}>
          <div className="absolute top-0 left-0 w-2 h-2 bg-violet-400 opacity-30 rounded-full"></div>
        </div>
        <div className="corner-element-animate top-4 right-4 sm:top-6 sm:right-6 md:top-8 md:right-8" style={{ animationDelay: '4.2s' }}>
          <div className="absolute top-0 right-0 w-2 h-2 bg-violet-400 opacity-30 rounded-full"></div>
        </div>
        <div className="corner-element-animate bottom-4 left-4 sm:bottom-6 sm:left-6 md:bottom-8 md:left-8" style={{ animationDelay: '4.4s' }}>
          <div className="absolute bottom-0 left-0 w-2 h-2 bg-violet-400 opacity-30 rounded-full"></div>
        </div>
        <div className="corner-element-animate bottom-4 right-4 sm:bottom-6 sm:right-6 md:bottom-8 md:right-8" style={{ animationDelay: '4.6s' }}>
          <div className="absolute bottom-0 right-0 w-2 h-2 bg-violet-400 opacity-30 rounded-full"></div>
        </div>

        {/* Floating Elements */}
        <div className="floating-element-animate" style={{ top: '25%', left: '15%', animationDelay: '0.5s' }}></div>
        <div className="floating-element-animate" style={{ top: '60%', left: '85%', animationDelay: '1s' }}></div>
        <div className="floating-element-animate" style={{ top: '40%', left: '10%', animationDelay: '1.5s' }}></div>
        <div className="floating-element-animate" style={{ top: '75%', left: '90%', animationDelay: '2s' }}></div>

        {/* Main Content */}
        <div className="relative z-10 min-h-[calc(100vh-4rem)] flex flex-col justify-between items-center px-6 py-10 sm:px-8 sm:py-12 md:px-16 md:py-16">
          
          {/* Header */}
          <div className="text-center">
            <h2 className="text-xs sm:text-sm font-mono font-light text-violet-300 uppercase tracking-[0.2em] opacity-80">
              <span className="word-animate" data-delay="0">AI</span>
              <span className="word-animate" data-delay="200">Agent</span>
              <span className="word-animate" data-delay="400">Marketplace</span>
            </h2>
            <div className="mt-4 w-12 sm:w-16 h-px bg-gradient-to-r from-transparent via-violet-400 to-transparent opacity-30 mx-auto"></div>
          </div>

          {/* Center - Orbital View */}
          <div className="flex-1 flex items-center justify-center w-full">
            <div className="relative">
              
              {/* Orbit Rings */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] h-[340px] rounded-full border border-violet-500/10 orbit-ring" />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[380px] h-[380px] rounded-full border border-violet-500/5" />
              
              {/* Butler - Center Agent */}
              <button
                onClick={(e) => { e.stopPropagation(); setShowButler(!showButler); setSelectedAgent(null); }}
                className="relative z-20 w-24 h-24 rounded-full bg-gradient-to-br from-violet-600 via-purple-600 to-indigo-600 flex items-center justify-center cursor-pointer transition-all duration-300 hover:scale-105"
                style={{ 
                  boxShadow: showButler 
                    ? '0 0 60px rgba(139, 92, 246, 0.5), 0 0 100px rgba(139, 92, 246, 0.3)' 
                    : '0 0 40px rgba(139, 92, 246, 0.3)' 
                }}
              >
                <div className="absolute w-28 h-28 rounded-full border border-violet-400/30 animate-ping opacity-30" style={{ animationDuration: '2s' }} />
                <div className="absolute w-32 h-32 rounded-full border border-violet-400/20 animate-ping opacity-20" style={{ animationDuration: '3s', animationDelay: '0.5s' }} />
                <div className="w-12 h-12 rounded-xl bg-white/90 flex items-center justify-center">
                  <Bot size={28} className="text-violet-600" />
                </div>
              </button>
              
              {/* Butler Label */}
              <div className="absolute top-full mt-4 left-1/2 -translate-x-1/2 text-center">
                <span className="text-sm font-medium text-violet-300 uppercase tracking-widest">Butler</span>
              </div>

              {/* Butler Info Panel */}
              {showButler && (() => {
                const ButlerIcon = getIcon(butler.icon);
                return (
                <div 
                  className="absolute top-32 left-1/2 -translate-x-1/2 w-72 bg-black/90 backdrop-blur-xl border border-violet-500/30 rounded-2xl p-5 z-30 shadow-xl shadow-violet-500/10"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Close Button */}
                  <button
                    onClick={(e) => { e.stopPropagation(); setShowButler(false); }}
                    className="absolute top-3 right-3 w-6 h-6 rounded-full bg-slate-800/80 hover:bg-slate-700 flex items-center justify-center transition-colors"
                  >
                    <X size={14} className="text-slate-400" />
                  </button>
                  
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
                      <Bot size={20} className="text-white" />
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-white">{butler.title}</h3>
                      <div className="flex items-center gap-1.5">
                        <div className={`w-1.5 h-1.5 rounded-full ${
                          butler.status === 'online' ? 'bg-green-500' : 
                          butler.status === 'busy' ? 'bg-yellow-500' : 'bg-red-500'
                        }`} />
                        <span className="text-xs text-slate-400 capitalize">{butler.status}</span>
                      </div>
                    </div>
                  </div>
                  <p className="text-sm text-slate-400 leading-relaxed mb-4">{butler.description}</p>
                  
                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-700/50">
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-1 text-violet-400 mb-1">
                        <Zap size={12} />
                        <span className="text-xs font-medium">Requests</span>
                      </div>
                      <span className="text-sm font-bold text-white">{butler.totalRequests.toLocaleString()}</span>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-1 text-yellow-400 mb-1">
                        <Star size={12} />
                        <span className="text-xs font-medium">Rating</span>
                      </div>
                      <span className="text-sm font-bold text-white">{butler.reputation}</span>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-1 text-green-400 mb-1">
                        <Activity size={12} />
                        <span className="text-xs font-medium">Success</span>
                      </div>
                      <span className="text-sm font-bold text-white">{butler.successRate}%</span>
                    </div>
                  </div>
                </div>
                );
              })()}

              {/* Loading State */}
              {loading && (
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 mt-32">
                  <Loader2 size={24} className="text-violet-400 animate-spin" />
                </div>
              )}

              {/* Orbiting Agents */}
              {agents.map((agent, index) => {
                const pos = getAgentPosition(index, agents.length);
                const Icon = getIcon(agent.icon);
                const isSelected = selectedAgent?.id === agent.id;
                
                return (
                  <button
                    key={agent.id}
                    onClick={(e) => { 
                      e.stopPropagation(); 
                      setSelectedAgent(isSelected ? null : agent); 
                      setShowButler(false);
                    }}
                    className="absolute top-1/2 left-1/2 transition-all duration-300 cursor-pointer"
                    style={{
                      transform: `translate(calc(-50% + ${pos.x}px), calc(-50% + ${pos.y}px)) scale(${isSelected ? 1.2 : pos.scale})`,
                      opacity: isSelected ? 1 : pos.opacity,
                      zIndex: isSelected ? 30 : 10,
                    }}
                  >
                    <div className={`w-14 h-14 rounded-full flex items-center justify-center transition-all duration-300 ${
                      isSelected 
                        ? 'bg-white shadow-lg shadow-violet-500/30' 
                        : 'bg-slate-800/80 border border-slate-700/50 hover:bg-slate-700/80'
                    }`}>
                      <Icon size={22} className={isSelected ? 'text-violet-600' : 'text-slate-300'} />
                    </div>
                    <div className={`absolute top-16 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-medium transition-all duration-300 ${
                      isSelected ? 'text-white' : 'text-slate-500'
                    }`}>
                      {agent.title}
                    </div>
                  </button>
                );
              })}

              {/* Selected Agent Info Panel */}
              {selectedAgent && (() => {
                const SelectedIcon = getIcon(selectedAgent.icon);
                return (
                <div 
                  className="absolute top-32 left-1/2 -translate-x-1/2 w-72 bg-black/90 backdrop-blur-xl border border-slate-700/50 rounded-2xl p-5 z-30 shadow-xl shadow-black/30"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Close Button */}
                  <button
                    onClick={(e) => { e.stopPropagation(); setSelectedAgent(null); }}
                    className="absolute top-3 right-3 w-6 h-6 rounded-full bg-slate-800/80 hover:bg-slate-700 flex items-center justify-center transition-colors"
                  >
                    <X size={14} className="text-slate-400" />
                  </button>
                  
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center">
                      <SelectedIcon size={20} className="text-slate-300" />
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-white">{selectedAgent.title}</h3>
                      <div className="flex items-center gap-1.5">
                        <div className={`w-1.5 h-1.5 rounded-full ${
                          selectedAgent.status === 'online' ? 'bg-green-500' : 
                          selectedAgent.status === 'busy' ? 'bg-yellow-500' : 'bg-red-500'
                        }`} />
                        <span className="text-xs text-slate-400 capitalize">{selectedAgent.status}</span>
                      </div>
                    </div>
                  </div>
                  <p className="text-sm text-slate-400 leading-relaxed mb-4">{selectedAgent.description}</p>
                  
                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-700/50">
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-1 text-violet-400 mb-1">
                        <Zap size={12} />
                        <span className="text-xs font-medium">Requests</span>
                      </div>
                      <span className="text-sm font-bold text-white">{selectedAgent.totalRequests.toLocaleString()}</span>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-1 text-yellow-400 mb-1">
                        <Star size={12} />
                        <span className="text-xs font-medium">Rating</span>
                      </div>
                      <span className="text-sm font-bold text-white">{selectedAgent.reputation}</span>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-1 text-green-400 mb-1">
                        <Activity size={12} />
                        <span className="text-xs font-medium">Success</span>
                      </div>
                      <span className="text-sm font-bold text-white">{selectedAgent.successRate}%</span>
                    </div>
                  </div>
                </div>
                );
              })()}
            </div>
          </div>

          {/* Footer Text */}
          <div className="text-center">
            <div className="mb-4 w-12 sm:w-16 h-px bg-gradient-to-r from-transparent via-violet-400 to-transparent opacity-30 mx-auto"></div>
            <h2 className="text-xs sm:text-sm font-mono font-light text-slate-400 uppercase tracking-[0.2em] opacity-80">
              <span className="word-animate" data-delay="3000">Orchestrate.</span>
              <span className="word-animate" data-delay="3200">Automate.</span>
              <span className="word-animate" data-delay="3400">Simplify.</span>
            </h2>

            {/* Scroll down indicator */}
            <button
              onClick={() => {
                document.getElementById('all-agents-section')?.scrollIntoView({ behavior: 'smooth' });
              }}
              className="mt-8 flex flex-col items-center gap-2 mx-auto group cursor-pointer"
            >
              <span className="text-sm text-slate-500 group-hover:text-violet-400 transition-colors tracking-wide">
                Scroll down to view all agents
              </span>
              <div className="w-5 h-8 rounded-full border border-slate-600 group-hover:border-violet-500/50 flex items-start justify-center pt-1.5 transition-colors">
                <div className="w-1 h-2 rounded-full bg-slate-500 group-hover:bg-violet-400 animate-bounce transition-colors" />
              </div>
            </button>
          </div>
        </div>

        {/* All Agents List Section */}
        <div id="all-agents-section" className="relative z-10 px-6 pb-16 sm:px-8 md:px-16">
          <div className="max-w-4xl mx-auto">
            {/* Section Header with Search */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mb-8">
              <div>
                <h3 className="text-xl font-semibold text-white text-center sm:text-left">All Agents</h3>
                <p className="text-sm text-slate-400 text-center sm:text-left">Browse and search available agents</p>
              </div>
              
              {/* Search Bar */}
              <div className="relative w-full sm:w-72">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search agents..."
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-800/60 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500/50 transition-colors"
                />
              </div>
            </div>

            {/* Agents Grid */}
            {filteredAgents.length === 0 ? (
              <div className="text-center py-12">
                <Bot size={40} className="text-slate-600 mx-auto mb-3" />
                <p className="text-slate-500">
                  {searchQuery ? 'No agents found matching your search' : 'No agents available'}
                </p>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {filteredAgents.map((agent) => {
                  const Icon = getIcon(agent.icon);
                  return (
                    <div
                      key={agent.id}
                      className="p-5 rounded-xl bg-slate-900/50 border border-slate-700/30 backdrop-blur-sm hover:border-violet-500/30 transition-all duration-300 group"
                    >
                      <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-xl bg-slate-800 flex items-center justify-center group-hover:bg-violet-500/20 transition-colors">
                          <Icon size={22} className="text-slate-400 group-hover:text-violet-400 transition-colors" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-semibold text-white truncate">{agent.title}</h4>
                            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                              agent.status === 'online' ? 'bg-green-500' : 
                              agent.status === 'busy' ? 'bg-yellow-500' : 'bg-red-500'
                            }`} />
                          </div>
                          <p className="text-sm text-slate-400 line-clamp-2 mb-3">{agent.description}</p>
                          
                          {/* Mini Stats */}
                          <div className="flex items-center gap-4 text-xs">
                            <div className="flex items-center gap-1 text-slate-500">
                              <Star size={12} className="text-yellow-500" />
                              <span>{agent.reputation.toFixed(1)}</span>
                            </div>
                            <div className="flex items-center gap-1 text-slate-500">
                              <Activity size={12} className="text-green-500" />
                              <span>{agent.successRate}%</span>
                            </div>
                            <div className="flex items-center gap-1 text-slate-500">
                              <Zap size={12} className="text-violet-400" />
                              <span>{agent.totalRequests.toLocaleString()} jobs</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Mouse Gradient */}
        <div 
          id="mouse-gradient-react"
          className="w-60 h-60 blur-xl sm:w-80 sm:h-80 sm:blur-2xl md:w-96 md:h-96 md:blur-3xl"
          style={{
            left: mouseGradientStyle.left,
            top: mouseGradientStyle.top,
            opacity: mouseGradientStyle.opacity,
          }}
        ></div>

        {/* Click Ripples */}
        {ripples.map(ripple => (
          <div
            key={ripple.id}
            className="ripple-effect"
            style={{ left: `${ripple.x}px`, top: `${ripple.y}px` }}
          ></div>
        ))}
      </div>
    </>
  );
};

export default AgentOrbitalLanding;
