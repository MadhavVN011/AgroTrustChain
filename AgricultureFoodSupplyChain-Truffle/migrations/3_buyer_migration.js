const Buyer = artifacts.require("BuyerContract.sol");
        module.exports = function (deployer) {
          deployer.deploy(Buyer);
        };
        