"""Calls to the AgroTrustChain contracts on Ethereum (Ganache) through Web3.py.

- TransactionDetailsContract: records transactions and anchors the hash chain.
- TraceabilityManagement: batches, compliance checks, Q/R scores and penalties.
"""
import datetime
import json
import os
import re

from web3 import Web3, HTTPProvider

import Constants


class BlockchainError(Exception):
    """Ethereum is unreachable, the contract is missing, or the call was rejected."""


class ContractRejected(BlockchainError):
    """The contract refused the call (a `require` failed). str() is the contract's reason."""


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


def _contract(name="TransactionDetailsContract", address_override=None):
    """Return (w3, contract, sender account) for a deployed contract."""
    w3, network_id = _connect()
    artifact_path = os.path.join(Constants.contracts_build_dir, name + ".json")
    try:
        with open(artifact_path) as file:
            artifact = json.load(file)
    except OSError as error:
        raise BlockchainError("Contract artifact not found at " + artifact_path + ". Run `truffle migrate`.") from error

    address = address_override or artifact.get("networks", {}).get(network_id, {}).get("address")
    if not address:
        raise BlockchainError(name + " is not deployed on Ethereum network " + network_id + ". Run `truffle migrate`.")
    address = _to_checksum(address)
    if not w3.eth.get_code(address):
        raise BlockchainError("No contract at " + address + " on network " + network_id
                              + ". The chain was probably reset: run `truffle migrate --reset`.")
    return w3, w3.eth.contract(address=address, abi=artifact["abi"]), w3.eth.accounts[0]


def _revert_reason(error):
    text = str(error)
    match = re.search(r"revert(?:ed)?:?\s*(.+?)(?:['\"]?\s*[,)}]|$)", text)
    return match.group(1).strip(" '\"") if match else text


def _send(w3, function, sender):
    # Dry-run first, so a failed `require` comes back with the contract's reason.
    try:
        function.call({"from": sender})
    except Exception as error:
        raise ContractRejected(_revert_reason(error)) from error
    try:
        tx_hash = function.transact({"from": sender})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    except Exception as error:
        raise BlockchainError("Ethereum transaction failed: " + str(error)) from error
    if receipt.get("status") == 0:
        raise BlockchainError("Ethereum transaction 0x" + bytes(tx_hash).hex() + " reverted.")
    return "0x" + bytes(tx_hash).hex()


# ---------------------------------------------------------------------------
# TransactionDetailsContract
# ---------------------------------------------------------------------------

def _transactions_contract():
    return _contract("TransactionDetailsContract", Constants.contract_address)


def record_transaction(agricultureBoardID, buyerID, farmerID, productID, price, qty):
    """Write a supply-chain transaction to the contract. Returns the Ethereum tx hash ("0x...")."""
    w3, contract, sender = _transactions_contract()
    function = contract.functions.perform_transactions(
        str(agricultureBoardID), str(buyerID), str(farmerID), str(productID), int(price), int(qty))
    return _send(w3, function, sender)


def anchor_chain(head_hash_hex, length):
    """Record the hash-chain tip (a 64-char hex SHA-256) and its length on Ethereum."""
    w3, contract, sender = _transactions_contract()
    head = bytes.fromhex(head_hash_hex) if head_hash_hex else bytes(32)
    if not hasattr(contract.functions, "anchorChain"):
        raise BlockchainError("The deployed TransactionDetailsContract predates chain anchoring. "
                              "Run `truffle migrate --reset` to deploy the current version.")
    return _send(w3, contract.functions.anchorChain(head, int(length)), sender)


def read_anchor():
    """Return {"head": 64-char hex or "", "length": int, "address": contract address}."""
    w3, contract, _ = _transactions_contract()
    try:
        head = bytes(contract.functions.chainHead().call())
        length = contract.functions.chainLength().call()
    except Exception as error:
        raise BlockchainError("Cannot read the chain anchor from the contract (" + str(error)
                              + "). If it predates chain anchoring, run `truffle migrate --reset`.") from error
    return {"head": "" if head == bytes(32) else head.hex(), "length": int(length), "address": contract.address}


# ---------------------------------------------------------------------------
# TraceabilityManagement: batches, compliance, Q/R scores, penalties
# ---------------------------------------------------------------------------

BATCH_STATUS = {0: "None", 1: "Pending", 2: "Validated", 3: "Revoked"}


def _traceability():
    return _contract("TraceabilityManagement")


def certificate_hash(certificate_number):
    """SHA-256 of the certificate identifier, as the 32 bytes stored on-chain."""
    import hashlib
    return hashlib.sha256(certificate_number.strip().encode("utf-8")).digest()


def _to_unix(date):
    if isinstance(date, str):
        date = datetime.date.fromisoformat(date)
    # Valid until the end of the expiry day (UTC).
    return int(datetime.datetime(date.year, date.month, date.day, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp())


def register_batch(batch_id, supplier_id, certificate_number, certificate_expiry, claimed_quality):
    """RegisterBatch. Raises ContractRejected with the reason if a compliance check fails."""
    w3, contract, sender = _traceability()
    function = contract.functions.registerBatch(
        str(batch_id), str(supplier_id), certificate_hash(certificate_number),
        _to_unix(certificate_expiry), int(claimed_quality))
    return _send(w3, function, sender)


def update_quality(batch_id, inspected_quality):
    """UpdateQuality. Returns {"txHash", "status", "consistent", "supplier": {...}} after the reputation rules ran."""
    w3, contract, sender = _traceability()
    batch_before = contract.functions.batches(str(batch_id)).call()
    supplier_id, claimed = batch_before[0], batch_before[3]
    before = supplier_scores([supplier_id])[supplier_id]
    tx_hash = _send(w3, contract.functions.updateQuality(str(batch_id), int(inspected_quality)), sender)
    after = supplier_scores([supplier_id])[supplier_id]
    batch_after = contract.functions.batches(str(batch_id)).call()
    tolerance = contract.functions.tolerance().call()
    return {
        "txHash": tx_hash,
        "status": BATCH_STATUS[batch_after[5]],
        "consistent": abs(int(claimed) - int(inspected_quality)) <= tolerance,
        "supplierId": supplier_id,
        "before": before,
        "supplier": after,
    }


def revoke_certificate(certificate_hash_hex):
    w3, contract, sender = _traceability()
    return _send(w3, contract.functions.revokeCertificate(bytes.fromhex(certificate_hash_hex)), sender)


def reinstate_supplier(supplier_id):
    w3, contract, sender = _traceability()
    return _send(w3, contract.functions.reinstateSupplier(str(supplier_id)), sender)


def is_eligible(supplier_id):
    _, contract, _ = _traceability()
    return bool(contract.functions.isEligible(str(supplier_id)).call())


def supplier_scores(supplier_ids):
    """{id: {"registered", "suspended", "q", "r", "weight", "batches", "penalties"}} read from the contract."""
    _, contract, _ = _traceability()
    scores = {}
    for supplier_id in supplier_ids:
        registered, suspended, q, r, batches, penalties = contract.functions.suppliers(str(supplier_id)).call()
        scores[supplier_id] = {
            "registered": registered, "suspended": suspended, "q": q, "r": r,
            "weight": contract.functions.weightOf(str(supplier_id)).call(),
            "batches": batches, "penalties": penalties,
        }
    return scores


def batch_validity(batch_ids):
    """{batch_id: bool} from isBatchValid (validated, certificate unrevoked and unexpired)."""
    _, contract, _ = _traceability()
    return {batch_id: bool(contract.functions.isBatchValid(str(batch_id)).call()) for batch_id in batch_ids}


def parameters():
    _, contract, _ = _traceability()
    names = ("alpha", "beta", "initialQuality", "initialReputation", "honestReward", "penalty",
             "tolerance", "minQuality", "suspendBelow")
    return {name: getattr(contract.functions, name)().call() for name in names}
