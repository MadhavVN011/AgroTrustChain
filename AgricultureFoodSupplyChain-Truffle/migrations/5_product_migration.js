const Product = artifacts.require("ProductContract.sol");
        module.exports = function (deployer) {
          deployer.deploy(Product);
        };
        