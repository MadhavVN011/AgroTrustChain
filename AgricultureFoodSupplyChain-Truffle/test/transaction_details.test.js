const TransactionDetailsContract = artifacts.require("TransactionDetailsContract");

contract("TransactionDetailsContract", (accounts) => {
  const [deployer, other] = accounts;
  let instance;

  beforeEach(async () => {
    instance = await TransactionDetailsContract.new({ from: deployer });
  });

  it("records the last transaction", async () => {
    await instance.perform_transactions("board-1", "buyer-1", "farmer-1", "product-1", 45, 10);
    assert.equal(await instance.agricultureBoardID(), "board-1");
    assert.equal(await instance.buyerID(), "buyer-1");
    assert.equal(await instance.farmerID(), "farmer-1");
    assert.equal(await instance.productID(), "product-1");
    assert.equal((await instance.price()).toNumber(), 45);
    assert.equal((await instance.qty()).toNumber(), 10);
  });

  it("starts with an empty chain anchor owned by the deployer", async () => {
    assert.equal(await instance.owner(), deployer);
    assert.equal((await instance.chainLength()).toNumber(), 0);
    assert.equal(await instance.chainHead(), "0x" + "0".repeat(64));
  });

  it("lets the deployer anchor the chain head and emits an event", async () => {
    const head = "0x" + "ab".repeat(32);
    const result = await instance.anchorChain(head, 3, { from: deployer });
    assert.equal(await instance.chainHead(), head);
    assert.equal((await instance.chainLength()).toNumber(), 3);
    const event = result.logs.find((log) => log.event === "ChainAnchored");
    assert.ok(event, "ChainAnchored event not emitted");
    assert.equal(event.args.chainLength.toNumber(), 3);
    assert.equal(event.args.chainHead, head);
  });

  it("rejects anchoring from any other account", async () => {
    const head = "0x" + "cd".repeat(32);
    let reverted = false;
    try {
      await instance.anchorChain(head, 1, { from: other });
    } catch (error) {
      reverted = /Only the deployer/.test(error.message);
    }
    assert.ok(reverted, "anchorChain from a non-owner should revert");
    assert.equal((await instance.chainLength()).toNumber(), 0);
  });
});
