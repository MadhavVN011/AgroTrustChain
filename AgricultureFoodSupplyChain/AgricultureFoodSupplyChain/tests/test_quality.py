"""Batches, inspections, reputation and the suspension check, with Ethereum faked."""
import pytest

import Blockchain
import Passwords
import AgricultureFoodSupplyChainV1Server as server
from test_app import FULL_ROLE, csrf, login, make_handler

NO_FARMER_ROLE = (3, "Clerk", 1, 1, 1, 1, 0, 1, 1)  # canFarmer = 0


class FakeChain:
    def __init__(self):
        self.eligible = True
        self.calls = []
        self.reject_with = None
        self.inspection = None

    def is_eligible(self, farmer_id):
        self.calls.append(("is_eligible", farmer_id))
        return self.eligible

    def register_batch(self, *args):
        self.calls.append(("register_batch",) + args)
        if self.reject_with:
            raise Blockchain.ContractRejected(self.reject_with)
        return "0x" + "ab" * 32

    def update_quality(self, batch_id, inspected):
        self.calls.append(("update_quality", batch_id, inspected))
        return self.inspection

    def supplier_scores(self, ids):
        return {i: {"registered": True, "suspended": i == "F2", "q": 70, "r": 12 if i == "F2" else 64,
                    "weight": 0 if i == "F2" else 67, "batches": 3, "penalties": 2 if i == "F2" else 0} for i in ids}

    def parameters(self):
        return {"alpha": 50, "beta": 50, "honestReward": 2, "penalty": 20, "tolerance": 10, "suspendBelow": 20}

    def batch_validity(self, ids):
        return {i: True for i in ids}

    def certificate_hash(self, number):
        return Blockchain.certificate_hash(number)


@pytest.fixture
def chain(monkeypatch):
    fake = FakeChain()
    for name in ("is_eligible", "register_batch", "update_quality", "supplier_scores", "parameters", "batch_validity"):
        monkeypatch.setattr(server.Blockchain, name, getattr(fake, name))
    return fake


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def logged_in(client, fake_db, role=FULL_ROLE, extra=None):
    base = make_handler(Passwords.hash_password("pw"), role=role)

    def handler(sql, params):
        if extra:
            rows = extra(sql, params)
            if rows is not None:
                return rows
        return base(sql, params)

    fake_db.handler = handler
    login(client)


def info_text(client):
    return client.get("/Information").get_data(as_text=True)


def test_quality_pages_need_the_farmer_permission(client, fake_db, chain):
    logged_in(client, fake_db, role=NO_FARMER_ROLE)
    for path in ("/BatchListing", "/Reputation", "/BatchOperation"):
        response = client.get(path)
        assert response.status_code == 302 and response.location.endswith("/Information"), path


def test_transaction_for_suspended_farmer_is_refused_before_any_write(client, fake_db, chain, monkeypatch):
    logged_in(client, fake_db)
    chain.eligible = False
    inserted = []
    monkeypatch.setattr(server.TransactionDetailsModel, "insert", staticmethod(lambda obj: inserted.append(obj)))
    response = client.post("/ProcessTransactionDetailsOperation", data={
        "csrf_token": csrf(client), "operation": "Create", "orderID": "", "agricultureBoardID": "AB", "gstNbr": "G",
        "buyerID": "B", "farmerID": "F2", "effDate": "2026-01-01", "productID": "P", "price": "1", "qty": "1"})
    assert response.location.endswith("/Information")
    assert inserted == []
    assert "suspended by the reputation engine" in info_text(client)


def test_batch_rejected_by_compliance_shows_the_contract_reason(client, fake_db, chain):
    logged_in(client, fake_db)
    chain.reject_with = "Certificate has expired"
    client.post("/ProcessBatchOperation", data={
        "csrf_token": csrf(client), "farmerID": "F1", "productID": "P1", "certificateNumber": "CERT-1",
        "certificateExpiry": "2030-01-01", "claimedQuality": "80"})
    assert "rejected by the compliance checks: Certificate has expired" in info_text(client)
    assert not [sql for sql, _ in fake_db.executed if sql.startswith("INSERT INTO Batch")]


def test_valid_batch_is_registered_on_chain_then_stored(client, fake_db, chain):
    logged_in(client, fake_db)
    response = client.post("/ProcessBatchOperation", data={
        "csrf_token": csrf(client), "farmerID": "F1", "productID": "P1", "certificateNumber": " CERT-1 ",
        "certificateExpiry": "2030-01-01", "claimedQuality": "80"})
    assert response.location.endswith("/BatchListing")
    call = next(c for c in chain.calls if c[0] == "register_batch")
    assert call[2:] == ("F1", "CERT-1", __import__("datetime").date(2030, 1, 1), 80)
    sql, params = next((s, p) for s, p in fake_db.executed if s.startswith("INSERT INTO Batch"))
    assert params[4] == Blockchain.certificate_hash("CERT-1").hex() and params[-1] == "0x" + "ab" * 32


@pytest.mark.parametrize("value", ["101", "-1", "abc", "50.5"])
def test_out_of_range_quality_is_refused(client, fake_db, chain, value):
    logged_in(client, fake_db)
    client.post("/ProcessBatchOperation", data={
        "csrf_token": csrf(client), "farmerID": "F1", "productID": "P1", "certificateNumber": "C",
        "certificateExpiry": "2030-01-01", "claimedQuality": value})
    assert "whole number from 0 to 100" in info_text(client)
    assert not [c for c in chain.calls if c[0] == "register_batch"]


def test_inconsistent_inspection_reports_penalty_and_suspension(client, fake_db, chain):
    logged_in(client, fake_db)
    chain.inspection = {"txHash": "0x1", "status": "Revoked", "consistent": False, "supplierId": "F1",
                        "before": {"r": 32, "suspended": False}, "supplier": {"r": 12, "suspended": True}}
    client.post("/ProcessBatchInspection", data={"csrf_token": csrf(client), "batchID": "BATCH-1", "inspectedQuality": "50"})
    page = info_text(client)
    assert "automatic penalty cut the farmer" in page and "from 32 to 12" in page
    assert "now suspended" in page
    sql, params = next((s, p) for s, p in fake_db.executed if s.startswith("UPDATE Batch SET inspectedQuality"))
    assert params == (50, "Revoked", "0x1", "BATCH-1")


def test_consistent_inspection_reports_reward(client, fake_db, chain):
    logged_in(client, fake_db)
    chain.inspection = {"txHash": "0x2", "status": "Validated", "consistent": True, "supplierId": "F1",
                        "before": {"r": 50, "suspended": False}, "supplier": {"r": 52, "suspended": False}}
    client.post("/ProcessBatchInspection", data={"csrf_token": csrf(client), "batchID": "BATCH-1", "inspectedQuality": "80"})
    assert "rose from 50 to 52" in info_text(client)


def test_reputation_page_shows_on_chain_scores(client, fake_db, chain):
    farmers = lambda sql, params: [("F1", "Green Valley"), ("F2", "Shady Acres")] if "FROM Farmer" in sql else None
    logged_in(client, fake_db, extra=farmers)
    page = client.get("/Reputation").get_data(as_text=True)
    assert "Green Valley" in page and "<b>67</b>" in page
    assert "Suspended" in page and "Reinstate" in page
    assert page.index("Green Valley") < page.index("Shady Acres")  # sorted by weight
