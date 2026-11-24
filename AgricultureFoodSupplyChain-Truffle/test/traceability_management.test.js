const TraceabilityManagement = artifacts.require("TraceabilityManagement");

const CERT = "0x" + "11".repeat(32);
const CERT2 = "0x" + "22".repeat(32);
const inOneYear = () => Math.floor(Date.now() / 1000) + 365 * 24 * 3600;

async function expectRevert(promise, reason) {
  try {
    await promise;
  } catch (error) {
    assert.include(error.message, reason, "wrong revert reason");
    return;
  }
  assert.fail("expected revert: " + reason);
}

async function supplier(instance, id) {
  const s = await instance.suppliers(id);
  return {
    registered: s.registered,
    suspended: s.suspended,
    q: Number(s.qualityScore),
    r: Number(s.reputationScore),
    batches: Number(s.batches),
    penalties: Number(s.penalties),
  };
}

contract("TraceabilityManagement", (accounts) => {
  const [owner, other] = accounts;
  let tm;

  beforeEach(async () => {
    tm = await TraceabilityManagement.new({ from: owner });
  });

  describe("compliance on registerBatch", () => {
    it("admits a compliant batch and registers the supplier with initial scores", async () => {
      await tm.registerBatch("B1", "F1", CERT, inOneYear(), 80);
      const s = await supplier(tm, "F1");
      assert.deepEqual([s.registered, s.q, s.r, s.batches], [true, 50, 50, 1]);
      const b = await tm.batches("B1");
      assert.equal(Number(b.status), 1); // Pending
    });

    it("rejects an expired certificate", async () => {
      await expectRevert(tm.registerBatch("B1", "F1", CERT, Math.floor(Date.now() / 1000) - 60, 80), "Certificate has expired");
    });

    it("rejects a revoked certificate", async () => {
      await tm.revokeCertificate(CERT);
      await expectRevert(tm.registerBatch("B1", "F1", CERT, inOneYear(), 80), "Certificate has been revoked");
    });

    it("rejects a missing certificate", async () => {
      await expectRevert(tm.registerBatch("B1", "F1", "0x" + "00".repeat(32), inOneYear(), 80), "Certificate hash required");
    });

    it("rejects quality below the minimum", async () => {
      await expectRevert(tm.registerBatch("B1", "F1", CERT, inOneYear(), 39), "below the minimum");
    });

    it("rejects a duplicate batch ID", async () => {
      await tm.registerBatch("B1", "F1", CERT, inOneYear(), 80);
      await expectRevert(tm.registerBatch("B1", "F1", CERT, inOneYear(), 80), "Batch already registered");
    });

    it("only lets the owner write", async () => {
      await expectRevert(tm.registerBatch("B1", "F1", CERT, inOneYear(), 80, { from: other }), "Only the owner");
      await expectRevert(tm.revokeCertificate(CERT, { from: other }), "Only the owner");
    });
  });

  describe("updateQuality: reputation and penalties", () => {
    it("rewards a consistent report and validates the batch", async () => {
      await tm.registerBatch("B1", "F1", CERT, inOneYear(), 80);
      const result = await tm.updateQuality("B1", 75); // |80 - 75| = 5 <= tolerance 10
      const s = await supplier(tm, "F1");
      assert.equal(s.r, 52);                 // 50 + 2
      assert.equal(s.q, 57);                 // (50*7 + 75*3) / 10 = 57.5 -> 57
      assert.equal(Number((await tm.batches("B1")).status), 2); // Validated
      assert.isTrue(await tm.isBatchValid("B1"));
      const ev = result.logs.find((l) => l.event === "QualityValidated");
      assert.isTrue(ev.args.consistent);
    });

    it("penalises an inconsistent report and revokes the batch", async () => {
      await tm.registerBatch("B1", "F1", CERT, inOneYear(), 95);
      const result = await tm.updateQuality("B1", 60); // |95 - 60| = 35 > 10
      const s = await supplier(tm, "F1");
      assert.equal(s.r, 30);                 // 50 - 20
      assert.equal(s.penalties, 1);
      assert.equal(Number((await tm.batches("B1")).status), 3); // Revoked
      assert.isFalse(await tm.isBatchValid("B1"));
      assert.ok(result.logs.find((l) => l.event === "PenaltyApplied"));
      assert.ok(result.logs.find((l) => l.event === "BatchRevoked"));
    });

    it("suspends a supplier whose R-Score falls below the threshold, blocking new batches", async () => {
      await tm.registerBatch("B1", "F1", CERT, inOneYear(), 95);
      await tm.updateQuality("B1", 50);      // R 50 -> 30
      await tm.registerBatch("B2", "F1", CERT, inOneYear(), 95);
      const result = await tm.updateQuality("B2", 50); // R 30 -> 10 < 20: suspended
      const s = await supplier(tm, "F1");
      assert.isTrue(s.suspended);
      assert.equal(s.r, 10);
      assert.isFalse(await tm.isEligible("F1"));
      assert.equal(Number(await tm.weightOf("F1")), 0);
      assert.ok(result.logs.find((l) => l.event === "SupplierSuspended"));
      await expectRevert(tm.registerBatch("B3", "F1", CERT, inOneYear(), 80), "Supplier is suspended");
    });

    it("reinstates a suspended supplier at the threshold", async () => {
      for (const id of ["B1", "B2"]) {
        await tm.registerBatch(id, "F1", CERT, inOneYear(), 95);
        await tm.updateQuality(id, 50);
      }
      await tm.reinstateSupplier("F1");
      const s = await supplier(tm, "F1");
      assert.isFalse(s.suspended);
      assert.equal(s.r, 20);
      assert.isTrue(await tm.isEligible("F1"));
    });

    it("revokes a consistent batch whose inspected quality fails the criterion, without a penalty", async () => {
      await tm.registerBatch("B1", "F1", CERT, inOneYear(), 45);
      await tm.updateQuality("B1", 38);      // consistent (7) but below minQuality 40
      const s = await supplier(tm, "F1");
      assert.equal(s.penalties, 0);
      assert.equal(s.r, 52);
      assert.equal(Number((await tm.batches("B1")).status), 3);
    });

    it("caps the R-Score at 100", async () => {
      for (let i = 0; i < 30; i++) {
        await tm.registerBatch("B" + i, "F1", CERT, inOneYear(), 90);
        await tm.updateQuality("B" + i, 90);
      }
      assert.equal((await supplier(tm, "F1")).r, 100);
    });

    it("refuses a second inspection of the same batch", async () => {
      await tm.registerBatch("B1", "F1", CERT, inOneYear(), 80);
      await tm.updateQuality("B1", 80);
      await expectRevert(tm.updateQuality("B1", 80), "not awaiting inspection");
    });
  });

  describe("weights and certificates", () => {
    it("computes W = (alpha*Q + beta*R) / 100", async () => {
      await tm.registerBatch("B1", "F1", CERT, inOneYear(), 80);
      await tm.updateQuality("B1", 80);      // Q = (350 + 240)/10 = 59, R = 52
      assert.equal(Number(await tm.weightOf("F1")), Math.floor((50 * 59 + 50 * 52) / 100));
      assert.equal(Number(await tm.weightOf("unknown")), 50); // initial weight for unregistered suppliers
    });

    it("invalidates validated batches when their certificate is revoked", async () => {
      await tm.registerBatch("B1", "F1", CERT2, inOneYear(), 80);
      await tm.updateQuality("B1", 80);
      assert.isTrue(await tm.isBatchValid("B1"));
      await tm.revokeCertificate(CERT2);
      assert.isFalse(await tm.isBatchValid("B1"));
    });

    it("validates parameters", async () => {
      await expectRevert(tm.setParameters(60, 50, 2, 20, 10, 40, 20), "alpha + beta must equal 100");
      await tm.setParameters(70, 30, 5, 25, 5, 50, 30);
      assert.equal(Number(await tm.alpha()), 70);
      assert.equal(Number(await tm.penalty()), 25);
    });
  });
});
