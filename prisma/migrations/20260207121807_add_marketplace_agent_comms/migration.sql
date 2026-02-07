-- AlterTable
ALTER TABLE "Agent" ADD COLUMN     "apiEndpoint" TEXT,
ADD COLUMN     "apiKey" TEXT,
ADD COLUMN     "capabilities" TEXT,
ADD COLUMN     "documentation" TEXT,
ADD COLUMN     "isVerified" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "onchainAddress" TEXT,
ADD COLUMN     "webhookUrl" TEXT;

-- CreateTable
CREATE TABLE "MarketplaceJob" (
    "id" SERIAL NOT NULL,
    "jobId" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "tags" TEXT[],
    "budgetUsdc" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "status" TEXT NOT NULL DEFAULT 'open',
    "poster" TEXT,
    "winner" TEXT,
    "winnerPrice" DOUBLE PRECISION,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "MarketplaceJob_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UserProfile" (
    "id" SERIAL NOT NULL,
    "userId" TEXT NOT NULL DEFAULT 'default',
    "fullName" TEXT,
    "email" TEXT,
    "phone" TEXT,
    "location" TEXT,
    "skills" TEXT,
    "experienceLevel" TEXT,
    "githubUrl" TEXT,
    "linkedinUrl" TEXT,
    "portfolioUrl" TEXT,
    "bio" TEXT,
    "preferences" JSONB,
    "extra" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "UserProfile_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AgentDataRequest" (
    "id" SERIAL NOT NULL,
    "requestId" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "agent" TEXT NOT NULL,
    "dataType" TEXT NOT NULL,
    "question" TEXT NOT NULL,
    "fields" TEXT[],
    "context" TEXT,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "answerData" JSONB,
    "answerMsg" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "answeredAt" TIMESTAMP(3),

    CONSTRAINT "AgentDataRequest_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AgentJobUpdate" (
    "id" SERIAL NOT NULL,
    "jobId" TEXT NOT NULL,
    "agent" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "data" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AgentJobUpdate_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "MarketplaceJob_jobId_key" ON "MarketplaceJob"("jobId");

-- CreateIndex
CREATE UNIQUE INDEX "UserProfile_userId_key" ON "UserProfile"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "AgentDataRequest_requestId_key" ON "AgentDataRequest"("requestId");

-- AddForeignKey
ALTER TABLE "AgentDataRequest" ADD CONSTRAINT "AgentDataRequest_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "MarketplaceJob"("jobId") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AgentJobUpdate" ADD CONSTRAINT "AgentJobUpdate_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "MarketplaceJob"("jobId") ON DELETE RESTRICT ON UPDATE CASCADE;
