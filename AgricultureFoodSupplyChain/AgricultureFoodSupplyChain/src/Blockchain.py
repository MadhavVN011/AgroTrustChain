"""Calls to the TransactionDetailsContract on Ethereum (Ganache) through Web3.py."""
import json
import os

from web3 import Web3, HTTPProvider

import Constants


class BlockchainError(Exception):
    """Ethereum is unreachable, or the contract is missing or out of date."""


def _to_checksum(address):
    convert = getattr(Web3, "to_checksum_address", None) or Web3.toChecksumAddress
    return convert(address)


def _connect():
    w3 = Web3(HTTPProvider(Constants.eth_rpc_url, request_kwargs={"timeout": 30}))
    try:
        network_id = str(w3.net.version)
    except Exception as error:
        raise BlockchainError("Cannot reach Ethereum at " + Constants.eth_rpc_url + " (" + str(error) + ").") from error
    return w3, network_id


def _contract():
    """Return (w3, contract, sender account) for the deployed TransactionDetailsContract."""
    w3, network_id = _connect()
    artifact_path = os.path.join(Constants.contracts_build_dir, "TransactionDetailsContract.json")
    try:
        with open(artifact_path) as file:
            artifact = json.load(file)
    except OSError as error:
        raise BlockchainError("Contract artifact not found at " + artifact_path + ". Run `truffle migrate`.") from error

    address = Constants.contract_address or artifact.get("networks", {}).get(network_id, {}).get("address")
    if not address:
        raise BlockchainError("TransactionDetailsContract is not deployed on Ethereum network " + network_id
                              + ". Run `truffle migrate`, or set CONTRACT_ADDRESS.")
    address = _to_checksum(address)
    if not w3.eth.get_code(address):
        raise BlockchainError("No contract at " + address + " on network " + network_id
                              + ". The chain was probably reset: run `truffle migrate --reset`.")
    return w3, w3.eth.contract(address=address, abi=artifact["abi"]), w3.eth.accounts[0]


def _send(w3, function, sender):
    try:
        tx_hash = function.transact({"from": sender})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    except BlockchainError:
        raise
    except Exception as error:
        raise BlockchainError("Ethereum transaction failed: " + str(error)) from error
    if receipt.get("status") == 0:
        raise BlockchainError("Ethereum transaction 0x" + bytes(tx_hash).hex() + " reverted.")
    return "0x" + bytes(tx_hash).hex()


def record_transaction(agricultureBoardID, buyerID, farmerID, productID, price, qty):
    """Write a supply-chain transaction to the contract. Returns the Ethereum tx hash ("0x...")."""
    w3, contract, sender = _contract()
    function = contract.functions.perform_transactions(
        str(agricultureBoardID), str(buyerID), str(farmerID), str(productID), int(price), int(qty))
    return _send(w3, function, sender)


def anchor_chain(head_hash_hex, length):
    """Record the hash-chain tip (a 64-char hex SHA-256) and its length on Ethereum."""
    w3, contract, sender = _contract()
    head = bytes.fromhex(head_hash_hex) if head_hash_hex else bytes(32)
    if not hasattr(contract.functions, "anchorChain"):
        raise BlockchainError("The deployed TransactionDetailsContract predates chain anchoring. "
                              "Run `truffle migrate --reset` to deploy the current version.")
    return _send(w3, contract.functions.anchorChain(head, int(length)), sender)


def read_anchor():
    """Return {"head": 64-char hex or "", "length": int, "address": contract address}."""
    w3, contract, _ = _contract()
    try:
        head = bytes(contract.functions.chainHead().call())
        length = contract.functions.chainLength().call()
    except Exception as error:
        raise BlockchainError("Cannot read the chain anchor from the contract (" + str(error)
                              + "). If it predates chain anchoring, run `truffle migrate --reset`.") from error
    return {"head": "" if head == bytes(32) else head.hex(), "length": int(length), "address": contract.address}
