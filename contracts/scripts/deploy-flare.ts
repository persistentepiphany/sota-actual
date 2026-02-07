import { config as dotenvConfig } from "dotenv";
import { ethers } from "hardhat";
import path from "path";
import { promises as fs } from "fs";

dotenvConfig({ path: path.resolve(__dirname, "..", "..", ".env") });

async function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
      console.log(
        `⏳ Retrying in ${delayMs}ms... (attempt ${i + 1}/${maxRetries})`
      );
      await delay(delayMs);
    }
  }
  throw new Error("Max retries exceeded");
}

async function main() {
  const [deployer] = await ethers.getSigners();
  const network = await deployer.provider!.getNetwork();
  const chainId = Number(network.chainId);

  // ─── Network Naming ─────────────────────────────────────
  let networkName: string;
  let nativeCurrency: string;
  if (chainId === 114) {
    networkName = "flare-coston2";
    nativeCurrency = "C2FLR";
  } else if (chainId === 14) {
    networkName = "flare-mainnet";
    nativeCurrency = "FLR";
  } else if (chainId === 31337) {
    networkName = "hardhat-local";
    nativeCurrency = "ETH";
  } else {
    networkName = `chain-${chainId}`;
    nativeCurrency = "ETH";
  }

  console.log(`\n🚀 Deploying SOTA Flare contracts to ${networkName} (Chain ID: ${chainId})`);
  console.log(`   Deployer: ${deployer.address}`);
  const balance = await deployer.provider!.getBalance(deployer.address);
  console.log(`   Balance:  ${ethers.formatEther(balance)} ${nativeCurrency}\n`);

  // ═══════════════════════════════════════════════════════════
  // 1. FTSO Price Consumer
  // ═══════════════════════════════════════════════════════════

  let ftsoAddress: string;

  if (chainId === 31337) {
    // Local: deploy MockFastUpdater + set a default FLR/USD price
    console.log("📦 Deploying MockFastUpdater (local mode)...");
    const mockUpdater = await retryWithBackoff(() =>
      ethers.deployContract("MockFastUpdater")
    );
    await retryWithBackoff(() => mockUpdater.waitForDeployment());
    console.log(`   MockFastUpdater: ${mockUpdater.target}`);

    // Set FLR/USD = $0.025 (feed index 0, 5 decimals → 2500)
    await retryWithBackoff(() =>
      (mockUpdater as any).setPrice(0, 2500, 5)
    );
    console.log("   Set FLR/USD = $0.025");
    await delay(1000);

    console.log("📦 Deploying FTSOPriceConsumer...");
    const ftso = await retryWithBackoff(() =>
      ethers.deployContract("FTSOPriceConsumer", [deployer.address])
    );
    await retryWithBackoff(() => ftso.waitForDeployment());

    // Point FTSO consumer at mock updater
    await retryWithBackoff(() =>
      (ftso as any).setFastUpdater(mockUpdater.target)
    );
    ftsoAddress = ftso.target as string;
    console.log(`   FTSOPriceConsumer: ${ftsoAddress}`);
  } else {
    // Flare networks: FTSO resolves from on-chain registry automatically
    console.log("📦 Deploying FTSOPriceConsumer (Flare mode — auto-resolves from registry)...");
    const ftso = await retryWithBackoff(() =>
      ethers.deployContract("FTSOPriceConsumer", [deployer.address])
    );
    await retryWithBackoff(() => ftso.waitForDeployment());
    ftsoAddress = ftso.target as string;
    console.log(`   FTSOPriceConsumer: ${ftsoAddress}`);
  }
  await delay(2000);

  // ═══════════════════════════════════════════════════════════
  // 2. FDC Verifier
  // ═══════════════════════════════════════════════════════════

  let fdcVerifierAddress: string;

  if (chainId === 31337) {
    console.log("📦 Deploying MockFdcVerification (local mode)...");
    const mockFdc = await retryWithBackoff(() =>
      ethers.deployContract("MockFdcVerification")
    );
    await retryWithBackoff(() => mockFdc.waitForDeployment());
    console.log(`   MockFdcVerification: ${mockFdc.target}`);
    await delay(1000);
  }

  console.log("📦 Deploying FDCVerifier...");
  const fdcVerifier = await retryWithBackoff(() =>
    ethers.deployContract("FDCVerifier", [deployer.address])
  );
  await retryWithBackoff(() => fdcVerifier.waitForDeployment());
  fdcVerifierAddress = fdcVerifier.target as string;
  console.log(`   FDCVerifier: ${fdcVerifierAddress}`);

  if (chainId === 31337) {
    // For local testing, set FDC verification to the mock
    // (the auto-resolution won't work on hardhat)
    // We'll use manualConfirmDelivery() for testing
    console.log("   (Local mode: use manualConfirmDelivery() for testing)");
  }
  await delay(2000);

  // ═══════════════════════════════════════════════════════════
  // 3. FlareOrderBook
  // ═══════════════════════════════════════════════════════════

  console.log("📦 Deploying FlareOrderBook...");
  const orderBook = await retryWithBackoff(() =>
    ethers.deployContract("FlareOrderBook", [deployer.address, ftsoAddress])
  );
  await retryWithBackoff(() => orderBook.waitForDeployment());
  const orderBookAddress = orderBook.target as string;
  console.log(`   FlareOrderBook: ${orderBookAddress}`);
  await delay(2000);

  // ═══════════════════════════════════════════════════════════
  // 4. FlareEscrow
  // ═══════════════════════════════════════════════════════════

  console.log("📦 Deploying FlareEscrow...");
  const escrow = await retryWithBackoff(() =>
    ethers.deployContract("FlareEscrow", [
      deployer.address,
      ftsoAddress,
      deployer.address, // fee collector = deployer for now
    ])
  );
  await retryWithBackoff(() => escrow.waitForDeployment());
  const escrowAddress = escrow.target as string;
  console.log(`   FlareEscrow: ${escrowAddress}`);
  await delay(2000);

  // ═══════════════════════════════════════════════════════════
  // 5. AgentRegistry (reuse existing contract)
  // ═══════════════════════════════════════════════════════════

  console.log("📦 Deploying AgentRegistry...");
  const agentRegistry = await retryWithBackoff(() =>
    ethers.deployContract("AgentRegistry", [deployer.address])
  );
  await retryWithBackoff(() => agentRegistry.waitForDeployment());
  const agentRegistryAddress = agentRegistry.target as string;
  console.log(`   AgentRegistry: ${agentRegistryAddress}`);
  await delay(2000);

  // ═══════════════════════════════════════════════════════════
  // 6. Wire contracts together
  // ═══════════════════════════════════════════════════════════

  console.log("\n🔗 Wiring contracts...");

  console.log("   FlareOrderBook.setEscrow → FlareEscrow");
  await retryWithBackoff(() => (orderBook as any).setEscrow(escrowAddress));
  await delay(2000);

  console.log("   FlareEscrow.setOrderBook → FlareOrderBook");
  await retryWithBackoff(() => (escrow as any).setOrderBook(orderBookAddress));
  await delay(2000);

  console.log("   FlareEscrow.setFdcVerifier → FDCVerifier");
  await retryWithBackoff(() =>
    (escrow as any).setFdcVerifier(fdcVerifierAddress)
  );
  await delay(2000);

  // Authorise the deployer as a submitter on FDCVerifier (for demo/testing)
  console.log("   FDCVerifier.setSubmitterAuthorised → deployer");
  await retryWithBackoff(() =>
    (fdcVerifier as any).setSubmitterAuthorised(deployer.address, true)
  );
  await delay(1000);

  // ═══════════════════════════════════════════════════════════
  // 7. Save deployment artifacts
  // ═══════════════════════════════════════════════════════════

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const deploymentRecord = {
    network: networkName,
    chainId,
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
    flareIntegration: {
      ftsoUsage: "FLR/USD price feed for job quoting and escrow funding validation",
      fdcUsage: "Web2 delivery-status attestation gates escrow release (trustless)",
    },
    contracts: {
      FTSOPriceConsumer: ftsoAddress,
      FDCVerifier: fdcVerifierAddress,
      FlareOrderBook: orderBookAddress,
      FlareEscrow: escrowAddress,
      AgentRegistry: agentRegistryAddress,
    },
  } as const;

  const deploymentsDir = path.join(__dirname, "..", "deployments");
  await fs.mkdir(deploymentsDir, { recursive: true });

  const timestampedPath = path.join(
    deploymentsDir,
    `${networkName}-${chainId}-${timestamp}.json`
  );
  await fs.writeFile(timestampedPath, JSON.stringify(deploymentRecord, null, 2));

  const latestPath = path.join(
    deploymentsDir,
    `${networkName}-${chainId}.json`
  );
  await fs.writeFile(latestPath, JSON.stringify(deploymentRecord, null, 2));

  console.log("\n✅ Deployment complete!");
  console.log("📄 Saved to:");
  console.log(`   ${timestampedPath}`);
  console.log(`   ${latestPath}`);

  console.log("\n📋 Contract Addresses:");
  console.log(`   FTSOPriceConsumer: ${ftsoAddress}`);
  console.log(`   FDCVerifier:      ${fdcVerifierAddress}`);
  console.log(`   FlareOrderBook:   ${orderBookAddress}`);
  console.log(`   FlareEscrow:      ${escrowAddress}`);
  console.log(`   AgentRegistry:    ${agentRegistryAddress}`);

  console.log("\n📖 Bounty Alignment:");
  console.log("   ✓ FTSO MAIN — createJob() converts USD→FLR via FTSO feed");
  console.log("   ✓ FDC MAIN  — releaseToProvider() gated on FDC attestation");
  console.log("   ✓ FDC BONUS — escrow release driven entirely by FDC, not backend");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
