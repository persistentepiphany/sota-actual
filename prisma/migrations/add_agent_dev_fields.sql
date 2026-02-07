-- Add agent API configuration fields
ALTER TABLE "Agent" ADD COLUMN "apiEndpoint" TEXT;
ALTER TABLE "Agent" ADD COLUMN "apiKey" TEXT;
ALTER TABLE "Agent" ADD COLUMN "capabilities" TEXT; -- JSON array of capabilities
ALTER TABLE "Agent" ADD COLUMN "webhookUrl" TEXT;
ALTER TABLE "Agent" ADD COLUMN "onchainAddress" TEXT; -- Flare AgentRegistry address
ALTER TABLE "Agent" ADD COLUMN "isVerified" BOOLEAN DEFAULT false;
ALTER TABLE "Agent" ADD COLUMN "documentation" TEXT; -- Markdown docs
