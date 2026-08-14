const Farmer = artifacts.require("FarmerContract.sol");
        module.exports = function (deployer) {
          deployer.deploy(Farmer);
        };
        