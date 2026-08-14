const AgricultureBoard = artifacts.require("AgricultureBoardContract.sol");
        module.exports = function (deployer) {
          deployer.deploy(AgricultureBoard);
        };
        