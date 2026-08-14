const TransactionDetails = artifacts.require("TransactionDetailsContract.sol");
        module.exports = function (deployer) {
          deployer.deploy(TransactionDetails);
        };
        