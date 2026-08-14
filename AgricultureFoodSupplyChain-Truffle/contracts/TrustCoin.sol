// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract TrustCoin {

    string public name = "TrustCoin";
    string public symbol = "TRC";
    uint public totalSupply = 500000;

    mapping(address => uint) public balanceOf;

    constructor() {
        balanceOf[msg.sender] = totalSupply;
    }

    function transfer(address to, uint amount) public {

        require(balanceOf[msg.sender] >= amount, "Insufficient Balance");

        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
    }
}