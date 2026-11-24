import datetime

import pytest

import HashChain
from HashChain import HASH_FIELDS, check_blocks, compute_block_hash, plan_seal


def make_row(n, sealed=False, seq=None):
    return {
        "orderID": "order-%d" % n,
        "agricultureBoardID": "board-1",
        "gstNbr": "GST-%d" % n,
        "buyerID": "buyer-1",
        "farmerID": "farmer-1",
        "effDate": datetime.date(2026, 1, n),
        "productID": "product-1",
        "price": 10.0 * n,
        "qty": float(n),
        "isBlockChainGenerated": sealed,
        "hash": "",
        "prevHash": "",
        "sequenceNumber": n if seq is None else seq,
        "ethTxHash": None,
    }


def sealed_chain(count):
    """Rows sealed through plan_seal, plus the anchor sealing would record."""
    rows = [make_row(n) for n in range(1, count + 1)]
    updates, head, length = plan_seal(rows)
    by_id = {u["orderID"]: u for u in updates}
    for row in rows:
        row.update(by_id[row["orderID"]], isBlockChainGenerated=True)
    return rows, {"head": head, "length": length}


def statuses(rows):
    return [row["status"] for row in rows]


# --- compute_block_hash -----------------------------------------------------

def test_hash_is_deterministic_and_hex():
    row = make_row(1)
    first = compute_block_hash(row, "")
    assert first == compute_block_hash(dict(row), "")
    assert len(first) == 64 and int(first, 16) >= 0


@pytest.mark.parametrize("field", HASH_FIELDS)
def test_every_field_changes_the_hash(field):
    row = make_row(1)
    changed = dict(row)
    value = row[field]
    if isinstance(value, datetime.date):
        changed[field] = value + datetime.timedelta(days=1)
    elif isinstance(value, (int, float)):
        changed[field] = value + 1
    else:
        changed[field] = value + "x"
    assert compute_block_hash(row, "") != compute_block_hash(changed, "")


def test_prev_hash_changes_the_hash():
    row = make_row(1)
    assert compute_block_hash(row, "") != compute_block_hash(row, "a" * 64)


def test_display_and_seal_columns_do_not_affect_the_hash():
    row = make_row(1)
    decorated = dict(row, farmerName="Someone", ethTxHash="0xabc", hash="x", status="valid")
    assert compute_block_hash(row, "") == compute_block_hash(decorated, "")


# --- plan_seal --------------------------------------------------------------

def test_plan_seal_links_new_blocks_from_genesis():
    rows = [make_row(n) for n in (1, 2, 3)]
    updates, head, length = plan_seal(rows)
    assert [u["orderID"] for u in updates] == ["order-1", "order-2", "order-3"]
    assert updates[0]["prevHash"] == ""
    assert updates[1]["prevHash"] == updates[0]["hash"]
    assert updates[2]["prevHash"] == updates[1]["hash"]
    assert head == updates[2]["hash"] and length == 3


def test_plan_seal_appends_after_existing_tip():
    rows, anchor = sealed_chain(2)
    rows.append(make_row(3))
    updates, head, length = plan_seal(rows)
    assert len(updates) == 1
    assert updates[0]["prevHash"] == anchor["head"]
    assert length == 3


def test_plan_seal_renumbers_legacy_duplicate_sequence_numbers():
    rows = [make_row(n, seq=0) for n in (1, 2, 3)]
    updates, _, _ = plan_seal(rows)
    numbers = [u["sequenceNumber"] for u in updates]
    assert numbers == sorted(numbers) and len(set(numbers)) == 3


def test_plan_seal_with_nothing_pending():
    rows, anchor = sealed_chain(2)
    updates, head, length = plan_seal(rows)
    assert updates == [] and head == anchor["head"] and length == 2


# --- check_blocks -----------------------------------------------------------

def test_untouched_chain_is_intact():
    rows, anchor = sealed_chain(4)
    rows.append(make_row(5))
    summary = check_blocks(rows, anchor)
    assert summary["intact"] and summary["anchor"] == "match"
    assert statuses(rows) == ["valid"] * 4 + ["pending"]
    assert [r["blockNumber"] for r in rows] == [1, 2, 3, 4, None]


def test_edited_field_flags_only_that_block():
    rows, anchor = sealed_chain(4)
    rows[1]["price"] = 1.0
    summary = check_blocks(rows, anchor)
    assert not summary["intact"]
    assert statuses(rows) == ["valid", "tampered", "valid", "valid"]
    assert "Data was changed" in rows[1]["problems"][0]


def test_deleted_block_breaks_the_next_link():
    rows, anchor = sealed_chain(4)
    del rows[1]
    summary = check_blocks(rows, anchor)
    assert not summary["intact"]
    assert statuses(rows) == ["valid", "tampered", "valid"]
    assert "Link broken" in rows[1]["problems"][0]


def test_reordered_blocks_are_flagged():
    rows, anchor = sealed_chain(3)
    rows[0], rows[1] = rows[1], rows[0]
    summary = check_blocks(rows, anchor)
    assert summary["tampered"] >= 1 and not summary["intact"]


def test_full_rewrite_passes_internal_checks_but_fails_the_anchor():
    rows, anchor = sealed_chain(4)
    rows[1]["price"] = 1.0
    prev = rows[0]["hash"]
    for row in rows[1:]:  # attacker recomputes every later hash
        row["prevHash"] = prev
        row["hash"] = compute_block_hash(row, prev)
        prev = row["hash"]
    summary = check_blocks(rows, anchor)
    assert summary["tampered"] == 0
    assert summary["anchor"] == "mismatch" and not summary["intact"]


def test_truncated_chain_fails_the_anchor():
    rows, anchor = sealed_chain(4)
    summary = check_blocks(rows[:-1], anchor)
    assert summary["tampered"] == 0
    assert summary["anchor"] == "mismatch" and not summary["intact"]


def test_never_anchored_chain_is_reported_as_missing():
    rows, _ = sealed_chain(2)
    summary = check_blocks(rows, {"head": "", "length": 0})
    assert summary["anchor"] == "missing" and summary["intact"]


def test_unreachable_ethereum_is_reported_as_unavailable():
    rows, _ = sealed_chain(2)
    summary = check_blocks(rows, {"error": "Cannot reach Ethereum"})
    assert summary["anchor"] == "unavailable"
    assert summary["anchorMessage"] == "Cannot reach Ethereum"


def test_empty_chain_matches_empty_anchor():
    summary = check_blocks([make_row(1)], {"head": "", "length": 0})
    assert summary["anchor"] == "match" and summary["pending"] == 1


# --- seal_pending_blocks (database and Ethereum faked) ---------------------

class FakeChain:
    def __init__(self, anchor):
        self.anchor = anchor
        self.anchored = []

    def read_anchor(self):
        return dict(self.anchor)

    def anchor_chain(self, head, length):
        self.anchored.append((head, length))
        self.anchor = {"head": head, "length": length}


def serve_rows(fake_db, rows):
    columns = list(rows[0].keys()) if rows else list(make_row(1).keys())

    def handler(sql, params):
        if sql.startswith("SELECT") and "WITH (UPDLOCK, HOLDLOCK)" in sql:
            return [tuple(row[c] for c in columns) for row in rows]
        return []

    fake_db.handler = handler
    fake_db.columns = columns


def test_seal_anchors_the_new_tip(fake_db, monkeypatch):
    rows, anchor = sealed_chain(2)
    rows.append(make_row(3))
    serve_rows(fake_db, rows)
    chain = FakeChain(anchor)
    monkeypatch.setattr(HashChain, "Blockchain", chain)
    assert HashChain.seal_pending_blocks() == 1
    assert chain.anchored and chain.anchored[-1][1] == 3
    updates = [p for sql, p in fake_db.executed if sql.startswith("UPDATE")]
    assert len(updates) == 1 and updates[0][1] == anchor["head"]


def test_seal_refuses_when_database_disagrees_with_anchor(fake_db, monkeypatch):
    rows, anchor = sealed_chain(3)
    rows = rows[:-1]  # last sealed block removed from the database
    rows.append(make_row(9))
    serve_rows(fake_db, rows)
    chain = FakeChain(anchor)
    monkeypatch.setattr(HashChain, "Blockchain", chain)
    with pytest.raises(HashChain.ChainIntegrityError):
        HashChain.seal_pending_blocks()
    assert chain.anchored == []
    assert not [sql for sql, _ in fake_db.executed if sql.startswith("UPDATE")]


def test_seal_anchors_a_verified_legacy_chain(fake_db, monkeypatch):
    rows, anchor = sealed_chain(2)
    serve_rows(fake_db, rows)
    chain = FakeChain({"head": "", "length": 0})
    monkeypatch.setattr(HashChain, "Blockchain", chain)
    assert HashChain.seal_pending_blocks() == 0
    assert chain.anchored == [(anchor["head"], 2)]
