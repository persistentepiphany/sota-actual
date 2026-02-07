"use client";

import { 
  Lightbulb, 
  Palette, 
  Code, 
  TestTube, 
  Rocket, 
  Users, 
  Shield, 
  Zap 
} from "lucide-react";
import ProjectTimeline from "@/components/ui/project-timeline";

const roadmapData = [
  {
    id: 1,
    title: "Ideation",
    date: "Q4 2025",
    content: "Initial concept development for SOTA - a decentralized AI agent marketplace on Flare Network with smart contract escrow and reputation systems.",
    category: "Planning",
    icon: Lightbulb,
    relatedIds: [2],
    status: "completed" as const,
    energy: 100,
  },
  {
    id: 2,
    title: "Architecture",
    date: "Q4 2025",
    content: "System architecture design including smart contracts, agent communication protocols, and multi-chain integration strategy.",
    category: "Design",
    icon: Palette,
    relatedIds: [1, 3],
    status: "completed" as const,
    energy: 100,
  },
  {
    id: 3,
    title: "Smart Contracts",
    date: "Q1 2026",
    content: "Development of FlareOrderBook, FlareEscrow, ReputationToken, and AgentRegistry contracts with FTSO price feeds integration.",
    category: "Development",
    icon: Code,
    relatedIds: [2, 4, 5],
    status: "completed" as const,
    energy: 100,
  },
  {
    id: 4,
    title: "Agent Framework",
    date: "Q1 2026",
    content: "Building the AI agent infrastructure with Butler orchestrator, specialized worker agents, and LangGraph-based workflows.",
    category: "Development",
    icon: Zap,
    relatedIds: [3, 5],
    status: "in-progress" as const,
    energy: 75,
  },
  {
    id: 5,
    title: "Testing & Audit",
    date: "Q1 2026",
    content: "Comprehensive testing on Coston2 testnet, security audits, and agent behavior validation under various scenarios.",
    category: "Testing",
    icon: TestTube,
    relatedIds: [3, 4, 6],
    status: "in-progress" as const,
    energy: 60,
  },
  {
    id: 6,
    title: "Beta Launch",
    date: "Q2 2026",
    content: "Limited beta release with select partners, gathering feedback and iterating on agent marketplace features.",
    category: "Release",
    icon: Users,
    relatedIds: [5, 7],
    status: "pending" as const,
    energy: 30,
  },
  {
    id: 7,
    title: "Security Hardening",
    date: "Q2 2026",
    content: "Enhanced security measures, rate limiting, fraud detection, and multi-sig governance implementation.",
    category: "Security",
    icon: Shield,
    relatedIds: [6, 8],
    status: "pending" as const,
    energy: 15,
  },
  {
    id: 8,
    title: "Mainnet Launch",
    date: "Q3 2026",
    content: "Full production deployment on Flare mainnet with public agent marketplace, staking rewards, and governance tokens.",
    category: "Release",
    icon: Rocket,
    relatedIds: [7],
    status: "pending" as const,
    energy: 5,
  },
];

export default function RoadmapPage() {
  return (
    <ProjectTimeline 
      timelineData={roadmapData} 
      centerLabel="SOTA"
    />
  );
}
