import { expect } from "chai";
import { ethers } from "hardhat";

describe("AgentStaking", function () {
  let deployer: any;
  let dev: any; // developer wallet who registers + stakes
  let agent: any; // operational agent address
  let poster: any;
  let other: any;
  let house: any; // house/bank wallet

  let agentRegistry: any;
  let mockRandom: any;
  let staking: any;

  // Helpers for FlareEscrow integration tests
  let mockUpdater: any;
  let ftso: any;
  let fdcVerifier: any;
  let orderBook: any;
  let escrow: any;

  const MINIMUM_STAKE = ethers.parseEther("50");
  const HOUSE_FEE_BPS = 500n; // 5%

  // Helper: compute house fee and net earnings
  function houseFee(amount: bigint): bigint {
    return (amount * HOUSE_FEE_BPS) / 10000n;
  }
  function netOf(amount: bigint): bigint {
    return amount - houseFee(amount);
  }

  async function currentTimestamp(): Promise<number> {
    const block = await ethers.provider.getBlock("latest");
    return block!.timestamp;
  }

  beforeEach(async function () {
    [deployer, dev, agent, poster, other, house] = await ethers.getSigners();

    // Deploy AgentRegistry
    agentRegistry = await ethers.deployContract("AgentRegistry", [
      deployer.address,
    ]);
    await agentRegistry.waitForDeployment();

    // Deploy MockRandomNumberV2
    mockRandom = await ethers.deployContract("MockRandomNumberV2");
    await mockRandom.waitForDeployment();

    // Set a fresh secure random with current timestamp
    const ts = await currentTimestamp();
    await mockRandom.setRandomNumber(42, true, ts);

    // Deploy AgentStaking
    staking = await ethers.deployContract("AgentStaking", [
      deployer.address,
      agentRegistry.target,
      mockRandom.target,
      MINIMUM_STAKE,
    ]);
    await staking.waitForDeployment();

    // Override hardcoded house wallet to a test signer
    await staking.connect(deployer).setHouseWallet(house.address);
  });

  // ─── Helper: developer registers an agent address ────────────
  async function registerAgent(developer: any, agentAddr: string) {
    await agentRegistry
      .connect(developer)
      .registerAgent(agentAddr, "TestAgent", "ipfs://meta", ["data_analysis"]);
  }

  // ─── Helper: developer deactivates an agent ─────────────────
  async function deactivateAgent(developer: any, agentAddr: string) {
    await agentRegistry
      .connect(developer)
      .updateAgent(agentAddr, "TestAgent", "ipfs://meta", ["data_analysis"], 2); // 2 = Inactive
  }

  // ═══════════════════════════════════════════════════════════
  // Staking
  // ═══════════════════════════════════════════════════════════

  describe("stake()", function () {
    it("should allow developer to stake for an active agent", async function () {
      await registerAgent(dev, agent.address);

      await expect(
        staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE })
      )
        .to.emit(staking, "Staked")
        .withArgs(agent.address, MINIMUM_STAKE);

      const info = await staking.getStakeInfo(agent.address);
      expect(info.isStaked).to.be.true;
      expect(info.stakedAmount).to.equal(MINIMUM_STAKE);
      expect(info.accumulatedEarnings).to.equal(0);
    });

    it("should reject stake below minimum", async function () {
      await registerAgent(dev, agent.address);

      await expect(
        staking.connect(dev).stake(agent.address, { value: ethers.parseEther("10") })
      ).to.be.revertedWith("AgentStaking: below minimum stake");
    });

    it("should reject stake if agent not active in registry", async function () {
      await expect(
        staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE })
      ).to.be.revertedWith("AgentStaking: not developer");
    });

    it("should reject double stake", async function () {
      await registerAgent(dev, agent.address);
      await staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE });

      await expect(
        staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE })
      ).to.be.revertedWith("AgentStaking: already staked");
    });

    it("should accept stake above minimum", async function () {
      await registerAgent(dev, agent.address);
      const amount = ethers.parseEther("100");

      await staking.connect(dev).stake(agent.address, { value: amount });

      const info = await staking.getStakeInfo(agent.address);
      expect(info.stakedAmount).to.equal(amount);
    });

    it("should reject non-developer from staking", async function () {
      await registerAgent(dev, agent.address);

      await expect(
        staking.connect(other).stake(agent.address, { value: MINIMUM_STAKE })
      ).to.be.revertedWith("AgentStaking: not developer");
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Credit Earnings
  // ═══════════════════════════════════════════════════════════

  describe("creditEarnings()", function () {
    beforeEach(async function () {
      await registerAgent(dev, agent.address);
      await staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE });

      // Set escrow to deployer for direct testing
      await staking.connect(deployer).setEscrow(deployer.address);
    });

    it("should credit earnings from escrow", async function () {
      const amount = ethers.parseEther("10");

      await expect(
        staking
          .connect(deployer)
          .creditEarnings(agent.address, amount, { value: amount })
      )
        .to.emit(staking, "EarningsCredited")
        .withArgs(agent.address, amount);

      const info = await staking.getStakeInfo(agent.address);
      expect(info.accumulatedEarnings).to.equal(amount);
    });

    it("should accumulate multiple earnings", async function () {
      const a1 = ethers.parseEther("5");
      const a2 = ethers.parseEther("15");

      await staking
        .connect(deployer)
        .creditEarnings(agent.address, a1, { value: a1 });
      await staking
        .connect(deployer)
        .creditEarnings(agent.address, a2, { value: a2 });

      const info = await staking.getStakeInfo(agent.address);
      expect(info.accumulatedEarnings).to.equal(a1 + a2);
    });

    it("should reject if caller is not escrow", async function () {
      const amount = ethers.parseEther("10");
      await expect(
        staking
          .connect(other)
          .creditEarnings(agent.address, amount, { value: amount })
      ).to.be.revertedWith("AgentStaking: caller is not escrow");
    });

    it("should reject value mismatch", async function () {
      await expect(
        staking
          .connect(deployer)
          .creditEarnings(agent.address, ethers.parseEther("10"), {
            value: ethers.parseEther("5"),
          })
      ).to.be.revertedWith("AgentStaking: value mismatch");
    });

    it("should reject if agent not staked", async function () {
      const amount = ethers.parseEther("10");
      await expect(
        staking
          .connect(deployer)
          .creditEarnings(other.address, amount, { value: amount })
      ).to.be.revertedWith("AgentStaking: agent not staked");
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Cashout (gamble)
  // ═══════════════════════════════════════════════════════════

  describe("cashout()", function () {
    const earnings = ethers.parseEther("10");

    beforeEach(async function () {
      await registerAgent(dev, agent.address);
      await staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE });
      await staking.connect(deployer).setEscrow(deployer.address);

      // Credit some earnings
      await staking
        .connect(deployer)
        .creditEarnings(agent.address, earnings, { value: earnings });
    });

    it("should pay net earnings on win when pool is empty (after 5% house fee)", async function () {
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, true, ts); // even -> win

      const fee = houseFee(earnings); // 0.5 FLR
      const net = netOf(earnings); // 9.5 FLR

      const houseBefore = await ethers.provider.getBalance(house.address);
      const balBefore = await ethers.provider.getBalance(dev.address);
      const tx = await staking.connect(dev).cashout(agent.address);
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const balAfter = await ethers.provider.getBalance(dev.address);
      const houseAfter = await ethers.provider.getBalance(house.address);

      // Pool is empty, bonus = 0, payout = net earnings only
      expect(balAfter - balBefore + gasCost).to.equal(net);
      // House received the fee
      expect(houseAfter - houseBefore).to.equal(fee);

      const info = await staking.getStakeInfo(agent.address);
      expect(info.accumulatedEarnings).to.equal(0);
      expect(info.wins).to.equal(1);
      expect(info.losses).to.equal(0);
    });

    it("should pay 2x net earnings on win when pool has enough", async function () {
      // Seed pool via another agent's loss
      await registerAgent(other, other.address);
      await staking.connect(other).stake(other.address, { value: MINIMUM_STAKE });
      const otherEarnings = ethers.parseEther("20");
      await staking
        .connect(deployer)
        .creditEarnings(other.address, otherEarnings, {
          value: otherEarnings,
        });

      // other loses -> net goes to pool
      let ts = await currentTimestamp();
      await mockRandom.setRandomNumber(43, true, ts); // odd -> lose
      await staking.connect(other).cashout(other.address);

      const otherNet = netOf(otherEarnings); // 19 FLR
      expect(await staking.getPoolSize()).to.equal(otherNet);

      // dev wins
      ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, true, ts); // even -> win

      const devNet = netOf(earnings); // 9.5 FLR
      // bonus = min(9.5, 19) = 9.5, payout = 9.5 + 9.5 = 19 FLR
      const expectedPayout = devNet * 2n;

      const balBefore = await ethers.provider.getBalance(dev.address);
      const tx = await staking.connect(dev).cashout(agent.address);
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const balAfter = await ethers.provider.getBalance(dev.address);

      expect(balAfter - balBefore + gasCost).to.equal(expectedPayout);

      // Pool decreased by devNet (the bonus)
      expect(await staking.getPoolSize()).to.equal(otherNet - devNet);

      const info = await staking.getStakeInfo(agent.address);
      expect(info.wins).to.equal(1);
    });

    it("should lose net earnings to pool on loss (after 5% house fee)", async function () {
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(43, true, ts); // odd -> lose

      const fee = houseFee(earnings); // 0.5 FLR
      const net = netOf(earnings); // 9.5 FLR

      const poolBefore = await staking.getPoolSize();

      await expect(staking.connect(dev).cashout(agent.address))
        .to.emit(staking, "CashoutLoss")
        .withArgs(agent.address, net);

      const poolAfter = await staking.getPoolSize();
      expect(poolAfter - poolBefore).to.equal(net);

      const info = await staking.getStakeInfo(agent.address);
      expect(info.accumulatedEarnings).to.equal(0);
      expect(info.losses).to.equal(1);
      expect(info.wins).to.equal(0);
    });

    it("should cap win bonus to available pool", async function () {
      // Seed pool with 3 FLR via loss
      const smallPool = ethers.parseEther("3");
      await registerAgent(other, other.address);
      await staking.connect(other).stake(other.address, { value: MINIMUM_STAKE });
      await staking
        .connect(deployer)
        .creditEarnings(other.address, smallPool, { value: smallPool });

      let ts = await currentTimestamp();
      await mockRandom.setRandomNumber(43, true, ts); // lose
      await staking.connect(other).cashout(other.address);

      const poolAfterLoss = netOf(smallPool); // 2.85 FLR
      expect(await staking.getPoolSize()).to.equal(poolAfterLoss);

      // dev wins -> net = 9.5, bonus = min(9.5, 2.85) = 2.85
      ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, true, ts); // win

      const devNet = netOf(earnings); // 9.5 FLR
      const expectedPayout = devNet + poolAfterLoss; // 9.5 + 2.85 = 12.35 FLR

      const balBefore = await ethers.provider.getBalance(dev.address);
      const tx = await staking.connect(dev).cashout(agent.address);
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const balAfter = await ethers.provider.getBalance(dev.address);

      expect(balAfter - balBefore + gasCost).to.equal(expectedPayout);

      // Pool should be empty
      expect(await staking.getPoolSize()).to.equal(0);
    });

    it("should reject cashout with no earnings", async function () {
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(43, true, ts);
      await staking.connect(dev).cashout(agent.address);

      await expect(staking.connect(dev).cashout(agent.address)).to.be.revertedWith(
        "AgentStaking: no earnings"
      );
    });

    it("should reject cashout if not staked", async function () {
      await expect(staking.connect(other).cashout(other.address)).to.be.revertedWith(
        "AgentStaking: not developer"
      );
    });

    it("should reject cashout with insecure random number", async function () {
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, false, ts);

      await expect(staking.connect(dev).cashout(agent.address)).to.be.revertedWith(
        "AgentStaking: random number not secure"
      );
    });

    it("should reject cashout with stale random number", async function () {
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, true, ts - 200);

      await expect(staking.connect(dev).cashout(agent.address)).to.be.revertedWith(
        "AgentStaking: random number too stale"
      );
    });

    it("should reject non-developer from cashing out", async function () {
      await expect(
        staking.connect(other).cashout(agent.address)
      ).to.be.revertedWith("AgentStaking: not developer");
    });

    it("should emit HouseFeePaid on cashout", async function () {
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, true, ts);

      const fee = houseFee(earnings);

      await expect(staking.connect(dev).cashout(agent.address))
        .to.emit(staking, "HouseFeePaid")
        .withArgs(agent.address, fee);
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Unstake
  // ═══════════════════════════════════════════════════════════

  describe("unstake()", function () {
    beforeEach(async function () {
      await registerAgent(dev, agent.address);
      await staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE });
    });

    it("should return stake to developer after deactivation", async function () {
      await deactivateAgent(dev, agent.address);

      const balBefore = await ethers.provider.getBalance(dev.address);
      const tx = await staking.connect(dev).unstake(agent.address);
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const balAfter = await ethers.provider.getBalance(dev.address);

      expect(balAfter - balBefore + gasCost).to.equal(MINIMUM_STAKE);

      const info = await staking.getStakeInfo(agent.address);
      expect(info.isStaked).to.be.false;
      expect(info.stakedAmount).to.equal(0);
    });

    it("should forfeit uncashed earnings to pool on unstake", async function () {
      await staking.connect(deployer).setEscrow(deployer.address);
      const earnings = ethers.parseEther("15");
      await staking
        .connect(deployer)
        .creditEarnings(agent.address, earnings, { value: earnings });

      await deactivateAgent(dev, agent.address);

      const poolBefore = await staking.getPoolSize();

      await expect(staking.connect(dev).unstake(agent.address))
        .to.emit(staking, "Unstaked")
        .withArgs(agent.address, MINIMUM_STAKE, earnings);

      const poolAfter = await staking.getPoolSize();
      expect(poolAfter - poolBefore).to.equal(earnings);
    });

    it("should reject unstake if agent is still active", async function () {
      await expect(staking.connect(dev).unstake(agent.address)).to.be.revertedWith(
        "AgentStaking: agent still active"
      );
    });

    it("should reject unstake if not staked", async function () {
      await expect(staking.connect(other).unstake(other.address)).to.be.revertedWith(
        "AgentStaking: not developer"
      );
    });

    it("should reject non-developer from unstaking", async function () {
      await deactivateAgent(dev, agent.address);

      await expect(
        staking.connect(other).unstake(agent.address)
      ).to.be.revertedWith("AgentStaking: not developer");
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Views
  // ═══════════════════════════════════════════════════════════

  describe("Views", function () {
    it("isStaked returns false for non-staked agent", async function () {
      expect(await staking.isStaked(agent.address)).to.be.false;
    });

    it("isStaked returns true for staked agent", async function () {
      await registerAgent(dev, agent.address);
      await staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE });
      expect(await staking.isStaked(agent.address)).to.be.true;
    });

    it("previewCashout returns correct values with house fee", async function () {
      await registerAgent(dev, agent.address);
      await staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE });
      await staking.connect(deployer).setEscrow(deployer.address);

      const earnings = ethers.parseEther("10");
      await staking
        .connect(deployer)
        .creditEarnings(agent.address, earnings, { value: earnings });

      const [previewEarnings, previewFee, maxPayout] = await staking.previewCashout(
        agent.address
      );
      const fee = houseFee(earnings); // 0.5 FLR
      const net = netOf(earnings); // 9.5 FLR
      // Pool is empty, so max payout = net (no bonus)
      expect(previewEarnings).to.equal(earnings);
      expect(previewFee).to.equal(fee);
      expect(maxPayout).to.equal(net);
    });

    it("getPoolSize returns accumulated loss pool", async function () {
      expect(await staking.getPoolSize()).to.equal(0);
    });
  });

  // ═══════════════════════════════════════════════════════════
  // House Wallet
  // ═══════════════════════════════════════════════════════════

  describe("House wallet", function () {
    it("should have correct default fee (5%)", async function () {
      expect(await staking.houseFeeBps()).to.equal(500);
    });

    it("should allow house wallet to seed the pool", async function () {
      const seed = ethers.parseEther("100");

      await expect(
        staking.connect(house).seedPool({ value: seed })
      )
        .to.emit(staking, "PoolSeeded")
        .withArgs(house.address, seed);

      expect(await staking.getPoolSize()).to.equal(seed);
    });

    it("should reject non-house from seeding pool", async function () {
      await expect(
        staking.connect(other).seedPool({ value: ethers.parseEther("10") })
      ).to.be.revertedWith("AgentStaking: not house wallet");
    });

    it("should allow house wallet to withdraw from pool", async function () {
      // Seed first
      const seed = ethers.parseEther("100");
      await staking.connect(house).seedPool({ value: seed });

      const withdrawAmt = ethers.parseEther("30");

      const balBefore = await ethers.provider.getBalance(house.address);
      const tx = await staking.connect(house).withdrawPool(withdrawAmt);
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const balAfter = await ethers.provider.getBalance(house.address);

      expect(balAfter - balBefore + gasCost).to.equal(withdrawAmt);
      expect(await staking.getPoolSize()).to.equal(seed - withdrawAmt);
    });

    it("should reject withdraw exceeding pool", async function () {
      await expect(
        staking.connect(house).withdrawPool(ethers.parseEther("1"))
      ).to.be.revertedWith("AgentStaking: exceeds pool");
    });

    it("should reject non-house from withdrawing", async function () {
      await staking.connect(house).seedPool({ value: ethers.parseEther("10") });

      await expect(
        staking.connect(other).withdrawPool(ethers.parseEther("5"))
      ).to.be.revertedWith("AgentStaking: not house wallet");
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Owner Config
  // ═══════════════════════════════════════════════════════════

  describe("Owner config", function () {
    it("should update minimum stake", async function () {
      const newMin = ethers.parseEther("100");
      await expect(staking.connect(deployer).setMinimumStake(newMin))
        .to.emit(staking, "MinimumStakeUpdated")
        .withArgs(newMin);
      expect(await staking.minimumStake()).to.equal(newMin);
    });

    it("should update escrow", async function () {
      await expect(staking.connect(deployer).setEscrow(other.address))
        .to.emit(staking, "EscrowUpdated")
        .withArgs(other.address);
      expect(await staking.escrow()).to.equal(other.address);
    });

    it("should update house wallet", async function () {
      await expect(staking.connect(deployer).setHouseWallet(other.address))
        .to.emit(staking, "HouseWalletUpdated")
        .withArgs(other.address);
      expect(await staking.houseWallet()).to.equal(other.address);
    });

    it("should reject zero address for house wallet", async function () {
      await expect(
        staking.connect(deployer).setHouseWallet(ethers.ZeroAddress)
      ).to.be.revertedWith("AgentStaking: zero address");
    });

    it("should update house fee", async function () {
      await expect(staking.connect(deployer).setHouseFeeBps(1000))
        .to.emit(staking, "HouseFeeUpdated")
        .withArgs(1000);
      expect(await staking.houseFeeBps()).to.equal(1000);
    });

    it("should reject house fee above 20%", async function () {
      await expect(
        staking.connect(deployer).setHouseFeeBps(2001)
      ).to.be.revertedWith("AgentStaking: fee too high");
    });

    it("should reject non-owner config changes", async function () {
      await expect(
        staking.connect(dev).setMinimumStake(100)
      ).to.be.revertedWithCustomError(staking, "OwnableUnauthorizedAccount");

      await expect(
        staking.connect(dev).setEscrow(dev.address)
      ).to.be.revertedWithCustomError(staking, "OwnableUnauthorizedAccount");

      await expect(
        staking.connect(dev).setHouseWallet(dev.address)
      ).to.be.revertedWithCustomError(staking, "OwnableUnauthorizedAccount");

      await expect(
        staking.connect(dev).setHouseFeeBps(100)
      ).to.be.revertedWithCustomError(staking, "OwnableUnauthorizedAccount");
    });
  });

  // ═══════════════════════════════════════════════════════════
  // FlareEscrow Integration (earnings routing)
  // ═══════════════════════════════════════════════════════════

  describe("FlareEscrow integration", function () {
    beforeEach(async function () {
      // Full deployment like flare-orderbook.test.ts
      mockUpdater = await ethers.deployContract("MockFastUpdater");
      await mockUpdater.waitForDeployment();
      await mockUpdater.setPrice(0, 2500, 5); // FLR/USD = $0.025

      ftso = await ethers.deployContract("FTSOPriceConsumer", [
        deployer.address,
      ]);
      await ftso.waitForDeployment();
      await ftso.setFastUpdater(mockUpdater.target);

      fdcVerifier = await ethers.deployContract("FDCVerifier", [
        deployer.address,
      ]);
      await fdcVerifier.waitForDeployment();

      orderBook = await ethers.deployContract("FlareOrderBook", [
        deployer.address,
        ftso.target,
      ]);
      await orderBook.waitForDeployment();

      escrow = await ethers.deployContract("FlareEscrow", [
        deployer.address,
        ftso.target,
        deployer.address,
      ]);
      await escrow.waitForDeployment();

      // Wire
      await orderBook.setEscrow(escrow.target);
      await escrow.setOrderBook(orderBook.target);
      await escrow.setFdcVerifier(fdcVerifier.target);

      // Wire staking <-> escrow
      await staking.setEscrow(escrow.target);
      await escrow.setAgentStaking(staking.target);
    });

    it("should route FLR payout to staking for staked provider", async function () {
      // Developer registers agent and stakes
      await registerAgent(dev, agent.address);
      await staking.connect(dev).stake(agent.address, { value: MINIMUM_STAKE });

      // Create and assign a job (agent is the operational provider)
      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;
      await orderBook
        .connect(poster)
        .createJob("ipfs://job", ethers.parseUnits("10", 18), deadline);
      await orderBook.connect(poster).assignProvider(1, agent.address);

      // Fund escrow: 10 USD => 400 FLR
      const flrNeeded = ethers.parseUnits("400", 18);
      await escrow
        .connect(poster)
        .fundJob(1, agent.address, ethers.parseUnits("10", 18), {
          value: flrNeeded,
        });

      // Agent completes work + FDC attest
      const proof = ethers.keccak256(ethers.toUtf8Bytes("done"));
      await orderBook.connect(agent).markCompleted(1, proof);
      await fdcVerifier.connect(deployer).manualConfirmDelivery(1);

      // Release -- should route to staking, not directly to agent
      await escrow.connect(poster).releaseToProvider(1);

      // 400 FLR - 2% escrow fee = 392 FLR credited as earnings
      const expectedEarnings = ethers.parseUnits("392", 18);
      const info = await staking.getStakeInfo(agent.address);
      expect(info.accumulatedEarnings).to.equal(expectedEarnings);
    });

    it("should pay directly to non-staked provider", async function () {
      // Developer registers agent but does NOT stake
      await registerAgent(dev, agent.address);

      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;
      await orderBook
        .connect(poster)
        .createJob("ipfs://job", ethers.parseUnits("10", 18), deadline);
      await orderBook.connect(poster).assignProvider(1, agent.address);

      const flrNeeded = ethers.parseUnits("400", 18);
      await escrow
        .connect(poster)
        .fundJob(1, agent.address, ethers.parseUnits("10", 18), {
          value: flrNeeded,
        });

      const proof = ethers.keccak256(ethers.toUtf8Bytes("done"));
      await orderBook.connect(agent).markCompleted(1, proof);
      await fdcVerifier.connect(deployer).manualConfirmDelivery(1);

      // Should go directly to agent (the provider address)
      const balBefore = await ethers.provider.getBalance(agent.address);
      await escrow.connect(poster).releaseToProvider(1);
      const balAfter = await ethers.provider.getBalance(agent.address);

      const expectedPayout = ethers.parseUnits("392", 18);
      expect(balAfter - balBefore).to.equal(expectedPayout);
    });
  });
});
