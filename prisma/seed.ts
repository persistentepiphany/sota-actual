import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";
import { createHash, randomBytes } from "crypto";

const prisma = new PrismaClient();

// Generate API key (same logic as auth.ts)
function generateApiKey(): { keyId: string; fullKey: string; keyHash: string } {
  const keyId = `ak_${randomBytes(8).toString("hex")}`;
  const secret = randomBytes(24).toString("hex");
  const fullKey = `${keyId}.${secret}`;
  const keyHash = createHash("sha256").update(fullKey).digest("hex");
  return { keyId, fullKey, keyHash };
}

async function main() {
  console.log("🧹 Cleaning database...");
  
  // Clear all existing data
  await prisma.agentApiKey.deleteMany({});
  await prisma.agentJobUpdate.deleteMany({});
  await prisma.agentDataRequest.deleteMany({});
  await prisma.marketplaceJob.deleteMany({});
  await prisma.order.deleteMany({});
  await prisma.agent.deleteMany({});
  await prisma.session.deleteMany({});
  await prisma.userProfile.deleteMany({});
  await prisma.callSummary.deleteMany({});
  
  console.log("✅ Database cleaned");

  // Create demo user
  const passwordHash = await bcrypt.hash("password123", 10);
  const user = await prisma.user.upsert({
    where: { email: "demo@sota.ai" },
    update: {},
    create: {
      email: "demo@sota.ai",
      name: "SOTA Developer",
      passwordHash,
      walletAddress: "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD48",
    },
  });

  console.log("👤 Created demo user:", user.email);

  // Create Caller Agent - Voice/Phone verification service
  const caller = await prisma.agent.create({
    data: {
      title: "Caller",
      description: "AI-powered phone verification and voice communication agent. Makes outbound calls for verification, reminders, and confirmations using natural language.",
      category: "Communication",
      priceUsd: 0.10,
      tags: "phone,twilio,verification,voice,calls",
      network: "flare-coston2",
      ownerId: user.id,
      status: "active",
      icon: "Phone",
      walletAddress: "0x8ba1f109551bD432803012645Ac136ddd64DBA72",
      apiEndpoint: "http://localhost:8000/api/v1/caller/execute",
      capabilities: JSON.stringify(["voice_call", "phone_verification", "outbound_calls", "natural_language"]),
      minFeeUsdc: 0.05,
      maxConcurrent: 10,
      isVerified: true,
      documentation: `# Caller Agent API

## Overview
The Caller agent makes AI-powered phone calls for verification, reminders, and confirmations.

## API Endpoint
\`POST /api/v1/caller/execute\`

## Request Body
\`\`\`json
{
  "phone_number": "+1234567890",
  "task": "verify_identity",
  "context": {
    "user_name": "John Doe",
    "verification_code": "123456"
  }
}
\`\`\`

## Response
\`\`\`json
{
  "call_sid": "CA...",
  "status": "completed",
  "duration": 45,
  "transcript": "..."
}
\`\`\`
`,
      totalRequests: 0,
      successfulRequests: 0,
      reputation: 5.0,
    },
  });

  // Create Hackathon Agent - Event discovery and registration
  const hackathon = await prisma.agent.create({
    data: {
      title: "Hackathon",
      description: "Discovers upcoming hackathons, tech events, and conferences. Automatically registers users based on their profile and preferences.",
      category: "Events",
      priceUsd: 0.05,
      tags: "events,hackathon,registration,discovery,tech",
      network: "flare-coston2",
      ownerId: user.id,
      status: "active",
      icon: "Calendar",
      walletAddress: "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
      apiEndpoint: "http://localhost:8000/api/v1/hackathon/execute",
      capabilities: JSON.stringify(["web_scrape", "event_discovery", "auto_registration", "data_analysis"]),
      minFeeUsdc: 0.03,
      maxConcurrent: 20,
      isVerified: true,
      documentation: `# Hackathon Agent API

## Overview
The Hackathon agent discovers and registers users for tech events, hackathons, and conferences.

## API Endpoint
\`POST /api/v1/hackathon/execute\`

## Request Body
\`\`\`json
{
  "task": "find_events",
  "filters": {
    "location": "Europe",
    "date_range": "next_3_months",
    "topics": ["AI", "blockchain", "web3"]
  },
  "user_profile": {
    "name": "John Doe",
    "email": "john@example.com",
    "skills": ["python", "solidity"]
  }
}
\`\`\`

## Response
\`\`\`json
{
  "events_found": 12,
  "registrations": [
    {
      "event": "ETHGlobal Brussels",
      "status": "registered",
      "confirmation": "..."
    }
  ]
}
\`\`\`
`,
      totalRequests: 0,
      successfulRequests: 0,
      reputation: 5.0,
    },
  });

  console.log("🤖 Created agents: Caller, Hackathon");

  // Generate API keys for both agents
  const callerKey = generateApiKey();
  const hackathonKey = generateApiKey();

  await prisma.agentApiKey.createMany({
    data: [
      {
        keyId: callerKey.keyId,
        keyHash: callerKey.keyHash,
        agentId: caller.id,
        name: "Production",
        permissions: ["execute", "bid"],
      },
      {
        keyId: hackathonKey.keyId,
        keyHash: hackathonKey.keyHash,
        agentId: hackathon.id,
        name: "Production",
        permissions: ["execute", "bid"],
      },
    ],
  });

  console.log("\n🔑 Generated API Keys (save these!):\n");
  console.log("┌─────────────────────────────────────────────────────────────────────────────┐");
  console.log("│ CALLER AGENT                                                                │");
  console.log("├─────────────────────────────────────────────────────────────────────────────┤");
  console.log(`│ Key ID:   ${callerKey.keyId.padEnd(65)}│`);
  console.log(`│ Full Key: ${callerKey.fullKey.substring(0, 60)}...│`);
  console.log("│                                                                             │");
  console.log("│ HACKATHON AGENT                                                             │");
  console.log("├─────────────────────────────────────────────────────────────────────────────┤");
  console.log(`│ Key ID:   ${hackathonKey.keyId.padEnd(65)}│`);
  console.log(`│ Full Key: ${hackathonKey.fullKey.substring(0, 60)}...│`);
  console.log("└─────────────────────────────────────────────────────────────────────────────┘");
  console.log("\n⚠️  Save these keys! They cannot be retrieved after this.\n");

  // Save keys to a local file for development
  const fs = await import("fs");
  const keysContent = `# SOTA Agent API Keys
# Generated: ${new Date().toISOString()}
# ⚠️  Keep these secret! Do not commit to version control.

CALLER_API_KEY=${callerKey.fullKey}
HACKATHON_API_KEY=${hackathonKey.fullKey}
`;

  fs.writeFileSync(".env.agent-keys", keysContent);
  console.log("📄 Keys saved to .env.agent-keys\n");

  console.log("✅ Seed completed successfully!");
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

