const AgroCoin = artifacts.require("AgroCoin");
const TrustCoin = artifacts.require("TrustCoin");

module.exports = function(deployer) {

    deployer.deploy(AgroCoin);

    deployer.deploy(TrustCoin);
};