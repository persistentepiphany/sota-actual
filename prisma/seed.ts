import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const existing = await prisma.user.findUnique({
    where: { email: "demo@swarm.ai" },
  });

  const passwordHash = await bcrypt.hash("password123", 10);

  const user =
    existing ??
    (await prisma.user.create({
      data: {
        email: "demo@swarm.ai",
        name: "Demo User",
        passwordHash,
      },
    }));

  // Orbital Dashboard Agents
  await prisma.agent.upsert({
    where: { id: 1 },
    update: { icon: "Bot", totalRequests: 156892, successfulRequests: 156735, reputation: 5.0 },
    create: {
      title: "Butler",
      description: "Your AI concierge orchestrating all agents",
      category: "Orchestration",
      priceUsd: 0,
      tags: "orchestration,ai,concierge",
      network: "flare-coston2",
      ownerId: user.id,
      status: "active",
      icon: "Bot",
      totalRequests: 156892,
      successfulRequests: 156735,
      reputation: 5.0,
    },
  });

  await prisma.agent.upsert({
    where: { id: 2 },
    update: { icon: "Phone", totalRequests: 12847, successfulRequests: 12615, reputation: 4.9 },
    create: {
      title: "Caller",
      description: "Phone verification via Twilio",
      category: "Communication",
      priceUsd: 15,
      tags: "phone,twilio,verification",
      network: "flare-coston2",
      ownerId: user.id,
      status: "active",
      icon: "Phone",
      totalRequests: 12847,
      successfulRequests: 12615,
      reputation: 4.9,
    },
  });

  await prisma.agent.upsert({
    where: { id: 3 },
    update: { icon: "Calendar", totalRequests: 8532, successfulRequests: 8233, reputation: 4.8 },
    create: {
      title: "Hackathon",
      description: "Event discovery & registration",
      category: "Events",
      priceUsd: 10,
      tags: "events,hackathon,registration",
      network: "flare-coston2",
      ownerId: user.id,
      status: "active",
      icon: "Calendar",
      totalRequests: 8532,
      successfulRequests: 8233,
      reputation: 4.8,
    },
  });

  await prisma.agent.upsert({
    where: { id: 4 },
    update: { icon: "Briefcase", totalRequests: 23491, successfulRequests: 22974, reputation: 4.7 },
    create: {
      title: "Manager",
      description: "Job orchestration & workflows",
      category: "Workflow",
      priceUsd: 25,
      tags: "workflow,jobs,orchestration",
      network: "flare-coston2",
      ownerId: user.id,
      status: "busy",
      icon: "Briefcase",
      totalRequests: 23491,
      successfulRequests: 22974,
      reputation: 4.7,
    },
  });

  // Sample Marketplace Jobs for Dashboard
  const jobs = [
    {
      jobId: "job-001",
      description: "Find and register for upcoming AI hackathons in Europe",
      tags: ["hackathon", "registration", "europe"],
      budgetUsdc: 50,
      status: "assigned",
      winner: "hackathon",
      winnerPrice: 25,
      metadata: { complexity: "moderate", progress: 65 },
    },
    {
      jobId: "job-002",
      description: "Make outbound calls to verify 50 user phone numbers",
      tags: ["phone", "verification", "batch"],
      budgetUsdc: 75,
      status: "assigned",
      winner: "caller",
      winnerPrice: 40,
      metadata: { complexity: "simple", progress: 82 },
    },
    {
      jobId: "job-003",
      description: "Orchestrate multi-agent workflow for customer onboarding",
      tags: ["workflow", "onboarding", "automation"],
      budgetUsdc: 120,
      status: "open",
      metadata: { complexity: "complex", progress: 0 },
    },
    {
      jobId: "job-004",
      description: "Schedule and coordinate team meetings across timezones",
      tags: ["calendar", "scheduling", "timezones"],
      budgetUsdc: 30,
      status: "completed",
      winner: "hackathon",
      winnerPrice: 20,
      metadata: { complexity: "simple", progress: 100 },
    },
    {
      jobId: "job-005",
      description: "Analyze sentiment from 1000 customer support tickets",
      tags: ["analysis", "sentiment", "nlp"],
      budgetUsdc: 200,
      status: "assigned",
      winner: "manager",
      winnerPrice: 150,
      metadata: { complexity: "expert", progress: 35 },
    },
    {
      jobId: "job-006",
      description: "Place verification call to confirm meeting attendance",
      tags: ["phone", "confirmation", "meeting"],
      budgetUsdc: 15,
      status: "completed",
      winner: "caller",
      winnerPrice: 10,
      metadata: { complexity: "simple", progress: 100 },
    },
    {
      jobId: "job-007",
      description: "Failed: Could not reach API endpoint for data sync",
      tags: ["api", "sync", "error"],
      budgetUsdc: 45,
      status: "cancelled",
      metadata: { complexity: "moderate", progress: 15, error: "API timeout" },
    },
  ];

  for (const job of jobs) {
    await prisma.marketplaceJob.upsert({
      where: { jobId: job.jobId },
      update: job,
      create: job,
    });
  }

  console.log("Seeded agents and marketplace jobs!");
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });

