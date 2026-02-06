import { expect } from "chai";
import { ethers } from "hardhat";
import { SignerWithProvider } from "ethers";

describe("SOTA Flare Contracts", function () {
  let deployer: any;
  let poster: any;
  let provider: any;

  let mockUpdater: any;
  let ftso: any;
  let fdcVerifier: any;
  let orderBook: any;
  let escrow: any;

  beforeEach(async function () {
    [deployer, poster, provider] = await ethers.getSigners();

    // ── Deploy MockFastUpdater & set FLR/USD = $0.025 ──
    mockUpdater = await ethers.deployContract("MockFastUpdater");
    await mockUpdater.waitForDeployment();
    // Feed index 0, price 2500, 5 decimals → 0.025 USD
    await mockUpdater.setPrice(0, 2500, 5);

    // ── Deploy FTSOPriceConsumer ──
    ftso = await ethers.deployContract("FTSOPriceConsumer", [deployer.address]);
    await ftso.waitForDeployment();
    await ftso.setFastUpdater(mockUpdater.target);

    // ── Deploy FDCVerifier ──
    fdcVerifier = await ethers.deployContract("FDCVerifier", [deployer.address]);
    await fdcVerifier.waitForDeployment();

    // ── Deploy FlareOrderBook ──
    orderBook = await ethers.deployContract("FlareOrderBook", [
      deployer.address,
      ftso.target,
    ]);
    await orderBook.waitForDeployment();

    // ── Deploy FlareEscrow ──
    escrow = await ethers.deployContract("FlareEscrow", [
      deployer.address,
      ftso.target,
      deployer.address, // fee collector
    ]);
    await escrow.waitForDeployment();

    // ── Wire together ──
    await orderBook.setEscrow(escrow.target);
    await escrow.setOrderBook(orderBook.target);
    await escrow.setFdcVerifier(fdcVerifier.target);
  });

  describe("FTSOPriceConsumer", function () {
    it("should return FLR/USD price", async function () {
      const [priceWei] = await ftso.getFlrUsdPrice();
      // 2500 with 5 decimals → 0.025 USD → 0.025e18 = 25e15
      expect(priceWei).to.equal(ethers.parseUnits("0.025", 18));
    });

    it("should convert USD to FLR", async function () {
      // 10 USD → 10 / 0.025 = 400 FLR
      const flr = await ftso.usdToFlr(ethers.parseUnits("10", 18));
      expect(flr).to.equal(ethers.parseUnits("400", 18));
    });

    it("should convert FLR to USD", async function () {
      // 400 FLR → 400 * 0.025 = 10 USD
      const usd = await ftso.flrToUsd(ethers.parseUnits("400", 18));
      expect(usd).to.equal(ethers.parseUnits("10", 18));
    });
  });

  describe("FlareOrderBook", function () {
    it("should create a job with FTSO-derived FLR price", async function () {
      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;

      const tx = await orderBook
        .connect(poster)
        .createJob("ipfs://job-meta", ethers.parseUnits("50", 18), deadline);

      const receipt = await tx.wait();
      const event = receipt.logs.find(
        (l: any) => l.fragment?.name === "JobCreated"
      );
      expect(event).to.not.be.undefined;

      const job = await orderBook.getJob(1);
      expect(job.poster).to.equal(poster.address);
      expect(job.maxPriceUsd).to.equal(ethers.parseUnits("50", 18));
      // 50 USD / 0.025 = 2000 FLR
      expect(job.maxPriceFlr).to.equal(ethers.parseUnits("2000", 18));
      expect(job.status).to.equal(0); // OPEN
    });

    it("should quote USD to FLR", async function () {
      const flr = await orderBook.quoteUsdToFlr(ethers.parseUnits("25", 18));
      // 25 / 0.025 = 1000 FLR
      expect(flr).to.equal(ethers.parseUnits("1000", 18));
    });

    it("should assign provider and mark completed", async function () {
      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;
      await orderBook
        .connect(poster)
        .createJob("ipfs://job", ethers.parseUnits("10", 18), deadline);

      await orderBook.connect(poster).assignProvider(1, provider.address);

      let job = await orderBook.getJob(1);
      expect(job.status).to.equal(1); // ASSIGNED
      expect(job.provider).to.equal(provider.address);

      const proofHash = ethers.keccak256(ethers.toUtf8Bytes("delivered"));
      await orderBook.connect(provider).markCompleted(1, proofHash);

      job = await orderBook.getJob(1);
      expect(job.status).to.equal(2); // COMPLETED
      expect(job.deliveryProof).to.equal(proofHash);
    });

    it("should reject non-poster from assigning", async function () {
      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;
      await orderBook
        .connect(poster)
        .createJob("ipfs://job", ethers.parseUnits("10", 18), deadline);

      await expect(
        orderBook.connect(provider).assignProvider(1, provider.address)
      ).to.be.revertedWith("FlareOrderBook: not poster");
    });

    it("should cancel an open job", async function () {
      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;
      await orderBook
        .connect(poster)
        .createJob("ipfs://job", ethers.parseUnits("10", 18), deadline);

      await orderBook.connect(poster).cancelJob(1);
      const job = await orderBook.getJob(1);
      expect(job.status).to.equal(4); // CANCELLED
    });
  });

  describe("FlareEscrow + FDC-gated release", function () {
    let jobId: number;

    beforeEach(async function () {
      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;

      // Create and assign job
      await orderBook
        .connect(poster)
        .createJob("ipfs://job", ethers.parseUnits("10", 18), deadline);
      jobId = 1;

      await orderBook.connect(poster).assignProvider(jobId, provider.address);
    });

    it("should fund job with FTSO-validated FLR amount", async function () {
      // 10 USD budget → 400 FLR needed at $0.025
      const flrNeeded = ethers.parseUnits("400", 18);

      await escrow
        .connect(poster)
        .fundJob(jobId, provider.address, ethers.parseUnits("10", 18), {
          value: flrNeeded,
        });

      const dep = await escrow.getDeposit(jobId);
      expect(dep.funded).to.be.true;
      expect(dep.poster).to.equal(poster.address);
      expect(dep.provider).to.equal(provider.address);
      expect(dep.amount).to.equal(flrNeeded);
    });

    it("should reject underfunded escrow", async function () {
      // Send only 100 FLR when 400 is needed (with 5% slippage = 380 min)
      await expect(
        escrow
          .connect(poster)
          .fundJob(jobId, provider.address, ethers.parseUnits("10", 18), {
            value: ethers.parseUnits("100", 18),
          })
      ).to.be.revertedWith("FlareEscrow: insufficient FLR for USD budget");
    });

    it("should block release without FDC confirmation", async function () {
      const flrNeeded = ethers.parseUnits("400", 18);
      await escrow
        .connect(poster)
        .fundJob(jobId, provider.address, ethers.parseUnits("10", 18), {
          value: flrNeeded,
        });

      // Mark completed by agent
      const proof = ethers.keccak256(ethers.toUtf8Bytes("done"));
      await orderBook.connect(provider).markCompleted(jobId, proof);

      // Try to release — should fail because FDC hasn't attested
      await expect(
        escrow.connect(poster).releaseToProvider(jobId)
      ).to.be.revertedWith("FlareEscrow: delivery not attested by FDC");
    });

    it("should release after FDC manual confirmation", async function () {
      const flrNeeded = ethers.parseUnits("400", 18);
      await escrow
        .connect(poster)
        .fundJob(jobId, provider.address, ethers.parseUnits("10", 18), {
          value: flrNeeded,
        });

      // Mark completed
      const proof = ethers.keccak256(ethers.toUtf8Bytes("done"));
      await orderBook.connect(provider).markCompleted(jobId, proof);

      // FDC owner manually confirms delivery (simulates FDC attestation)
      await fdcVerifier.connect(deployer).manualConfirmDelivery(jobId);

      // Now release should work
      const balBefore = await ethers.provider.getBalance(provider.address);
      await escrow.connect(poster).releaseToProvider(jobId);
      const balAfter = await ethers.provider.getBalance(provider.address);

      // Provider should have received payout (400 FLR minus 2% fee = 392 FLR)
      const expectedPayout = ethers.parseUnits("392", 18);
      expect(balAfter - balBefore).to.equal(expectedPayout);

      // Job should be marked released
      const job = await orderBook.getJob(jobId);
      expect(job.status).to.equal(3); // RELEASED
    });

    it("should refund poster on dispute", async function () {
      const flrNeeded = ethers.parseUnits("400", 18);
      await escrow
        .connect(poster)
        .fundJob(jobId, provider.address, ethers.parseUnits("10", 18), {
          value: flrNeeded,
        });

      const balBefore = await ethers.provider.getBalance(poster.address);
      await escrow.connect(deployer).refund(jobId);
      const balAfter = await ethers.provider.getBalance(poster.address);

      expect(balAfter - balBefore).to.equal(flrNeeded);

      const dep = await escrow.getDeposit(jobId);
      expect(dep.refunded).to.be.true;
    });
  });

  describe("Full End-to-End Flow", function () {
    it("should complete create → fund → complete → FDC attest → release", async function () {
      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;

      // 1. Create job (FTSO quotes price)
      await orderBook
        .connect(poster)
        .createJob(
          "ipfs://book-hotel-oxford",
          ethers.parseUnits("50", 18),
          deadline
        );

      const job1 = await orderBook.getJob(1);
      expect(job1.maxPriceFlr).to.equal(ethers.parseUnits("2000", 18));

      // 2. Assign agent
      await orderBook.connect(poster).assignProvider(1, provider.address);

      // 3. Fund escrow (FTSO validates amount)
      await escrow
        .connect(poster)
        .fundJob(1, provider.address, ethers.parseUnits("50", 18), {
          value: ethers.parseUnits("2000", 18),
        });

      // 4. Agent completes work
      const proof = ethers.keccak256(ethers.toUtf8Bytes("hotel-booked"));
      await orderBook.connect(provider).markCompleted(1, proof);

      // 5. FDC attests delivery (in production: agent submits Merkle proof)
      await fdcVerifier.connect(deployer).manualConfirmDelivery(1);

      // 6. Release payment
      const balBefore = await ethers.provider.getBalance(provider.address);
      await escrow.connect(provider).releaseToProvider(1);
      const balAfter = await ethers.provider.getBalance(provider.address);

      // 2000 FLR - 2% fee = 1960 FLR (minus gas)
      const gain = balAfter - balBefore;
      expect(gain).to.be.gt(ethers.parseUnits("1959", 18)); // accounting for gas

      // 7. Verify final state
      const finalJob = await orderBook.getJob(1);
      expect(finalJob.status).to.equal(3); // RELEASED
    });
  });
});
