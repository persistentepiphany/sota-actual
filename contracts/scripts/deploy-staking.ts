/**
 * Deploy ONLY AgentStaking to Coston2 and wire it to existing contracts.
 *
 * Usage:
 *   npx hardhat run scripts/deploy-staking.ts --network flareCoston2
 */
import { config as dotenvConfig } from "dotenv";
import { ethers } from "hardhat";
import path from "path";
import { promises as fs } from "fs";

dotenvConfig({ path: path.resolve(__dirname, "..", "..", ".env") });

// Existing deployed addresses on Coston2
const EXISTING = {
  AgentRegistry: "0x46aDDBd334de452746443798d32C7C7C5fC8Dd16",
  FlareEscrow: "0xA961AA0d21C2F24a20B6bdAD683f1DaFA45CFc73",
  RandomNumberV2: "0x5CdF9eAF3EB8b44fB696984a1420B56A7575D250",
};

async function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries = 5,
  baseDelay = 2000
): Promise<T> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error: any) {
      const isRetryable =
        error?.message?.includes("Too Many Requests") ||
        error?.code === "ECONNRESET" ||
        error?.code === "ETIMEDOUT";
      if (!isRetryable || i === maxRetries - 1) throw error;
      const delayMs = baseDelay * Math.pow(2, i);
      console.log(`Retrying in ${delayMs}ms... (attempt ${i + 1}/${maxRetries})`);
      await delay(delayMs);
    }
  }
  throw new Error("Max retries exceeded");
}

async function main() {
  const [deployer] = await ethers.getSigners();
  const balance = await deployer.provider!.getBalance(deployer.address);

  console.log(`\nDeploying AgentStaking to Coston2`);
  console.log(`  Deployer: ${deployer.address}`);
  console.log(`  Balance:  ${ethers.formatEther(balance)} C2FLR\n`);

  // 1. Deploy AgentStaking
  console.log("Deploying AgentStaking...");
  const staking = await retryWithBackoff(() =>
    ethers.deployContract("AgentStaking", [
      deployer.address,           // initialOwner
      EXISTING.AgentRegistry,     // agentRegistry_
      EXISTING.RandomNumberV2,    // randomNumberV2_
      ethers.parseEther("50"),    // minimumStake_ (50 FLR)
    ])
  );
  await retryWithBackoff(() => staking.waitForDeployment());
  const stakingAddr = staking.target as string;
  console.log(`  AgentStaking deployed: ${stakingAddr}`);
  await delay(3000);

  // 2. Wire: AgentStaking.setEscrow -> FlareEscrow
  console.log("Setting escrow on AgentStaking...");
  const tx1 = await retryWithBackoff(() =>
    (staking as any).setEscrow(EXISTING.FlareEscrow)
  );
  await tx1.wait();
  console.log(`  AgentStaking.setEscrow -> ${EXISTING.FlareEscrow}`);
  await delay(3000);

  // 3. Wire: FlareEscrow.setAgentStaking -> AgentStaking
  console.log("Setting AgentStaking on FlareEscrow...");
  const escrow = await ethers.getContractAt("FlareEscrow", EXISTING.FlareEscrow);
  const tx2 = await retryWithBackoff(() =>
    (escrow as any).setAgentStaking(stakingAddr)
  );
  await tx2.wait();
  console.log(`  FlareEscrow.setAgentStaking -> ${stakingAddr}`);

  // 4. Update the deployment JSON
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  const latestPath = path.join(deploymentsDir, "flare-coston2-114.json");
  const existing = JSON.parse(await fs.readFile(latestPath, "utf-8"));
  existing.contracts.AgentStaking = stakingAddr;
  existing.contracts.RandomNumberV2 = EXISTING.RandomNumberV2;
  existing.deployedAt = new Date().toISOString();
  if (!existing.flareIntegration.randomNumberV2Usage) {
    existing.flareIntegration.randomNumberV2Usage =
      "50/50 cashout gamble on agent earnings via RandomNumberV2";
  }
  await fs.writeFile(latestPath, JSON.stringify(existing, null, 2));

  console.log(`\nDone! AgentStaking: ${stakingAddr}`);
  console.log(`Updated ${latestPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
