import os
import re

from wthraft.reputation import PARAMS, Supplier, record_inspection, weight

SOL = os.path.join(os.path.dirname(__file__), "..", "..", "AgricultureFoodSupplyChain-Truffle", "contracts",
                   "TraceabilityManagement.sol")


def test_constants_match_the_contract():
    source = open(SOL).read()
    for name, value in PARAMS.items():
        match = re.search(r"uint8 public %s = (\d+);" % name, source)
        assert match, "%s not found in the contract" % name
        assert int(match.group(1)) == value, name


def test_consistent_report_matches_contract_arithmetic():
    s = Supplier()
    record_inspection(s, consistent=True, inspected_quality=75)
    assert (s.q, s.r, s.penalties) == (57, 52, 0)  # same numbers as the Truffle test


def test_two_inconsistent_reports_suspend_and_zero_the_weight():
    s = Supplier()
    record_inspection(s, False, 50)
    assert (s.r, s.suspended) == (30, False)
    record_inspection(s, False, 50)
    assert (s.r, s.suspended, s.penalties) == (10, True, 2)
    assert weight(s) == 0


def test_reputation_is_capped():
    s = Supplier()
    for _ in range(40):
        record_inspection(s, True, 90)
    assert s.r == 100


def test_weight_formula():
    s = Supplier(q=59, r=52)
    assert weight(s) == (50 * 59 + 50 * 52) // 100
