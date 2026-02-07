-- AlterTable
ALTER TABLE "Agent" ADD COLUMN     "apiKeyHash" TEXT,
ADD COLUMN     "bidAggressiveness" DOUBLE PRECISION NOT NULL DEFAULT 0.8,
ADD COLUMN     "maxConcurrent" INTEGER NOT NULL DEFAULT 5,
ADD COLUMN     "minFeeUsdc" DOUBLE PRECISION NOT NULL DEFAULT 0.01;

-- CreateTable
CREATE TABLE "AgentApiKey" (
    "id" SERIAL NOT NULL,
    "keyId" TEXT NOT NULL,
    "keyHash" TEXT NOT NULL,
    "agentId" INTEGER NOT NULL,
    "name" TEXT NOT NULL DEFAULT 'Default',
    "permissions" TEXT[] DEFAULT ARRAY['execute', 'bid']::TEXT[],
    "lastUsedAt" TIMESTAMP(3),
    "expiresAt" TIMESTAMP(3),
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AgentApiKey_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Session" (
    "id" SERIAL NOT NULL,
    "sessionId" TEXT NOT NULL,
    "userId" INTEGER NOT NULL,
    "walletAddress" TEXT,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Session_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "AgentApiKey_keyId_key" ON "AgentApiKey"("keyId");

-- CreateIndex
CREATE INDEX "AgentApiKey_keyHash_idx" ON "AgentApiKey"("keyHash");

-- CreateIndex
CREATE UNIQUE INDEX "Session_sessionId_key" ON "Session"("sessionId");

-- CreateIndex
CREATE INDEX "Session_userId_idx" ON "Session"("userId");

-- AddForeignKey
ALTER TABLE "AgentApiKey" ADD CONSTRAINT "AgentApiKey_agentId_fkey" FOREIGN KEY ("agentId") REFERENCES "Agent"("id") ON DELETE CASCADE ON UPDATE CASCADE;
