"""Python mirror of the TraceabilityManagement contract's scoring rules.

The constants and the integer arithmetic match
AgricultureFoodSupplyChain-Truffle/contracts/TraceabilityManagement.sol
(tests/test_reputation.py checks the constants against the Solidity source), so
the simulation exercises the same rules the contract enforces.
"""
from dataclasses import dataclass

PARAMS = {
    "alpha": 50,
    "beta": 50,
    "initialQuality": 50,
    "initialReputation": 50,
    "honestReward": 2,
    "penalty": 20,
    "tolerance": 10,
    "minQuality": 40,
    "suspendBelow": 20,
}
MAX_SCORE = 100


@dataclass
class Supplier:
    q: int = PARAMS["initialQuality"]
    r: int = PARAMS["initialReputation"]
    suspended: bool = False
    penalties: int = 0


def weight(supplier, params=PARAMS):
    """W = (alpha * Q + beta * R) / 100, or 0 while suspended (contract: weightOf)."""
    if supplier.suspended:
        return 0
    return (params["alpha"] * supplier.q + params["beta"] * supplier.r) // 100


def record_inspection(supplier, consistent, inspected_quality, params=PARAMS):
    """Apply one inspection result (contract: updateQuality)."""
    supplier.q = (supplier.q * 7 + int(inspected_quality) * 3) // 10
    if consistent:
        supplier.r = min(MAX_SCORE, supplier.r + params["honestReward"])
        return
    supplier.r = max(0, supplier.r - params["penalty"])
    supplier.penalties += 1
    if supplier.r < params["suspendBelow"]:
        supplier.suspended = True
