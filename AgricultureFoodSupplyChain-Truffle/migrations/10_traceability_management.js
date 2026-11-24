const TraceabilityManagement = artifacts.require("TraceabilityManagement");

module.exports = function (deployer) {
  deployer.deploy(TraceabilityManagement);
};
