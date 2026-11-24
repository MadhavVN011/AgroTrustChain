"""Tamper-evident hash chain over TransactionDetails.

Each sealed transaction stores
    hash     = SHA-256 of (every business field + sequenceNumber + prevHash)
    prevHash = hash of the previous sealed transaction (by sequenceNumber)

Because each hash covers prevHash, the rows form a real chain: the report
recomputes every hash and checks every link, so a modified, deleted or
re-ordered sealed row is flagged.

Limitation: someone with write access to the database who rewrites a block
*and recomputes every later hash* produces a self-consistent chain. Detecting
that needs the latest hash anchored somewhere they cannot write, such as the
Ethereum contract.
"""
import datetime
import hashlib
import json

import pyodbc

from Constants import connString

# Columns covered by the hash, besides prevHash.
HASH_FIELDS = (
    "orderID", "agricultureBoardID", "gstNbr", "buyerID", "farmerID",
    "effDate", "productID", "price", "qty", "sequenceNumber",
)

_COLUMNS = (
    "td.orderID, td.agricultureBoardID, td.gstNbr, td.buyerID, td.farmerID, td.effDate, "
    "td.productID, td.price, td.qty, td.isBlockChainGenerated, td.hash, td.prevHash, td.sequenceNumber"
)
# Stable order, even for legacy rows that share a sequenceNumber.
_ORDER = "ORDER BY td.sequenceNumber, td.effDate, td.orderID"


def _canonical(value):
    if value is None:
        return ""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, float):
        return repr(value)
    return str(value)


def compute_block_hash(record, prev_hash):
    payload = {field: _canonical(record[field]) for field in HASH_FIELDS}
    payload["prevHash"] = prev_hash or ""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _fetch_dicts(cursor):
    names = [col[0] for col in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def count_blocks():
    """Return (sealed, pending) transaction counts."""
    conn = pyodbc.connect(connString, autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT "
            "SUM(CASE WHEN isBlockChainGenerated = 1 THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN isBlockChainGenerated = 1 THEN 0 ELSE 1 END) "
            "FROM TransactionDetails"
        )
        sealed, pending = cursor.fetchone()
        return sealed or 0, pending or 0
    finally:
        conn.close()


def seal_pending_blocks():
    """Append every unsealed transaction to the chain. Returns how many were sealed.

    Runs in one database transaction holding range locks on the table, so two
    concurrent requests cannot both extend the same tip.
    """
    conn = pyodbc.connect(connString, autocommit=False)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT " + _COLUMNS + " FROM TransactionDetails td WITH (UPDLOCK, HOLDLOCK) " + _ORDER
        )
        rows = _fetch_dicts(cursor)
        sealed = [r for r in rows if r["isBlockChainGenerated"]]
        pending = [r for r in rows if not r["isBlockChainGenerated"]]

        prev_hash = sealed[-1]["hash"] if sealed else ""
        tip_seq = sealed[-1]["sequenceNumber"] if sealed else None
        max_seq = max((r["sequenceNumber"] for r in rows), default=0)

        for record in pending:
            # A pending row must come after the tip in sequence order, or the
            # chain could not be walked by sequenceNumber. Unsealed rows have
            # no hash yet, so renumbering them is safe.
            if tip_seq is not None and record["sequenceNumber"] <= tip_seq:
                max_seq += 1
                record["sequenceNumber"] = max_seq
            block_hash = compute_block_hash(record, prev_hash)
            cursor.execute(
                "UPDATE TransactionDetails SET isBlockChainGenerated = 1, hash = ?, prevHash = ?, "
                "sequenceNumber = ? WHERE orderID = ?",
                (block_hash, prev_hash, record["sequenceNumber"], record["orderID"]),
            )
            prev_hash = block_hash
            tip_seq = record["sequenceNumber"]

        conn.commit()
        return len(pending)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_chain():
    """Load every transaction and check the chain.

    Returns (blocks, summary). Each block is a dict of the row's columns plus
    display names and
        status:   "valid", "tampered" or "pending"
        problems: list of human-readable reasons (empty unless tampered)
    """
    conn = pyodbc.connect(connString, autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT " + _COLUMNS + ", ab.agricultureBoardName, b.buyerName, f.farmerName, p.productName "
            "FROM TransactionDetails td "
            "LEFT JOIN AgricultureBoard ab ON ab.agricultureBoardID = td.agricultureBoardID "
            "LEFT JOIN Buyer b ON b.buyerID = td.buyerID "
            "LEFT JOIN Farmer f ON f.farmerID = td.farmerID "
            "LEFT JOIN Product p ON p.productID = td.productID " + _ORDER
        )
        blocks = _fetch_dicts(cursor)
    finally:
        conn.close()

    expected_prev = ""
    block_number = 0
    summary = {"valid": 0, "tampered": 0, "pending": 0}
    for block in blocks:
        block["problems"] = []
        if not block["isBlockChainGenerated"]:
            block["status"] = "pending"
            block["blockNumber"] = None
            summary["pending"] += 1
            continue

        block_number += 1
        block["blockNumber"] = block_number
        stored_hash = block["hash"] or ""
        stored_prev = block["prevHash"] or ""
        if stored_hash != compute_block_hash(block, stored_prev):
            block["problems"].append("Data was changed after this block was sealed (hash does not match its contents).")
        if stored_prev != expected_prev:
            block["problems"].append("Link broken: prevHash does not match the previous block's hash "
                                     "(a block before it was removed, re-sealed or re-ordered).")
        block["status"] = "tampered" if block["problems"] else "valid"
        summary[block["status"]] += 1
        expected_prev = stored_hash

    summary["intact"] = summary["tampered"] == 0
    return blocks, summary
