"""Tamper-evident hash chain over TransactionDetails.

Each sealed transaction stores
    hash     = SHA-256 of (every business field + sequenceNumber + prevHash)
    prevHash = hash of the previous sealed transaction (by sequenceNumber)

Because each hash covers prevHash, the rows form a real chain: the report
recomputes every hash and checks every link, so a modified, deleted or
re-ordered sealed row is flagged.

Every time blocks are sealed, the tip of the chain (its last hash and its
length) is also anchored in the TransactionDetailsContract on Ethereum. A
database chain that was rewritten and fully re-hashed verifies internally,
but no longer matches the anchor.

The pure functions (compute_block_hash, plan_seal, check_blocks) hold all the
logic and are unit-tested; the others add database and Ethereum access.
"""
import datetime
import hashlib
import json

import pyodbc

import Blockchain
from Constants import connString

# Columns covered by the hash, besides prevHash.
HASH_FIELDS = (
    "orderID", "agricultureBoardID", "gstNbr", "buyerID", "farmerID",
    "effDate", "productID", "price", "qty", "sequenceNumber",
)

_COLUMNS = (
    "td.orderID, td.agricultureBoardID, td.gstNbr, td.buyerID, td.farmerID, td.effDate, "
    "td.productID, td.price, td.qty, td.isBlockChainGenerated, td.hash, td.prevHash, td.sequenceNumber, td.ethTxHash"
)
# Stable order, even for legacy rows that share a sequenceNumber.
_ORDER = "ORDER BY td.sequenceNumber, td.effDate, td.orderID"


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------

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


def plan_seal(rows):
    """Work out how to append the unsealed rows to the chain.

    rows: every transaction, as dicts, in sequence order.
    Returns (updates, head, length): updates is a list of dicts with orderID,
    hash, prevHash and sequenceNumber for each newly sealed row; head and
    length describe the chain afterwards.
    """
    sealed = [r for r in rows if r["isBlockChainGenerated"]]
    pending = [r for r in rows if not r["isBlockChainGenerated"]]

    prev_hash = (sealed[-1]["hash"] or "") if sealed else ""
    tip_seq = sealed[-1]["sequenceNumber"] if sealed else None
    max_seq = max((r["sequenceNumber"] for r in rows), default=0)

    updates = []
    for row in pending:
        record = dict(row)
        # A pending row must come after the tip in sequence order, or the
        # chain could not be walked by sequenceNumber. Unsealed rows have no
        # hash yet, so renumbering them is safe.
        if tip_seq is not None and record["sequenceNumber"] <= tip_seq:
            max_seq += 1
            record["sequenceNumber"] = max_seq
        block_hash = compute_block_hash(record, prev_hash)
        updates.append({"orderID": record["orderID"], "hash": block_hash,
                        "prevHash": prev_hash, "sequenceNumber": record["sequenceNumber"]})
        prev_hash = block_hash
        tip_seq = record["sequenceNumber"]

    return updates, prev_hash, len(sealed) + len(updates)


def check_blocks(blocks, anchor):
    """Verify the chain.

    blocks: every transaction, as dicts, in sequence order.
    anchor: {"head": hex, "length": int} read from Ethereum, or
            {"error": message} if it could not be read.

    Adds to each block: status ("valid", "tampered" or "pending"), problems
    (list of reasons) and blockNumber. Returns a summary dict.
    """
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

    head, length = expected_prev, block_number
    summary["head"], summary["length"] = head, length

    # Compare the database chain's tip with the one anchored on Ethereum.
    if anchor is None or "error" in anchor:
        summary["anchor"] = "unavailable"
        summary["anchorMessage"] = (anchor or {}).get("error", "The Ethereum anchor was not checked.")
    elif anchor["length"] == 0 and length == 0:
        summary["anchor"] = "match"
    elif anchor["length"] == 0:
        summary["anchor"] = "missing"
        summary["anchorMessage"] = ("This chain has never been anchored on Ethereum, so a full rewrite of it "
                                    "cannot be ruled out. Generate Blocks anchors it.")
    elif anchor["head"] == head and anchor["length"] == length:
        summary["anchor"] = "match"
    else:
        summary["anchor"] = "mismatch"
        summary["anchorMessage"] = (
            "The chain in the database does not match the one anchored on Ethereum: the database has "
            + str(length) + " sealed block(s) ending in " + (head[:16] or "nothing") + "..., Ethereum records "
            + str(anchor["length"]) + " ending in " + (anchor["head"][:16] or "nothing")
            + "... Blocks were removed, added or rewritten outside the app."
        )

    summary["intact"] = summary["tampered"] == 0 and summary["anchor"] != "mismatch"
    return summary


# ---------------------------------------------------------------------------
# Database and Ethereum access
# ---------------------------------------------------------------------------

def _fetch_dicts(cursor):
    names = [col[0] for col in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _read_anchor_or_error():
    try:
        return Blockchain.read_anchor()
    except Blockchain.BlockchainError as error:
        return {"error": str(error)}


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


class ChainIntegrityError(Exception):
    """Sealing was refused because the existing chain does not match its Ethereum anchor."""


def seal_pending_blocks():
    """Append every unsealed transaction to the chain and anchor the new tip on Ethereum.

    Returns how many transactions were sealed. Runs in one database
    transaction holding range locks on the table, so two concurrent requests
    cannot both extend the same tip. If anchoring fails, nothing is sealed and
    Blockchain.BlockchainError is raised.

    Sealing is refused (ChainIntegrityError) when the existing chain does not
    match its anchor, since anchoring a new tip on top of it would hide the
    rewrite. A chain sealed before anchoring existed is anchored on the next
    run, but only if it verifies.
    """
    conn = pyodbc.connect(connString, autocommit=False)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT " + _COLUMNS + " FROM TransactionDetails td WITH (UPDLOCK, HOLDLOCK) " + _ORDER
        )
        rows = _fetch_dicts(cursor)

        existing = check_blocks([dict(r) for r in rows], Blockchain.read_anchor())
        if existing["anchor"] == "mismatch":
            raise ChainIntegrityError(existing["anchorMessage"] + " New blocks were not sealed, so the "
                                      "evidence is preserved. Investigate on the Blockchain Report.")
        if existing["anchor"] == "missing" and existing["tampered"]:
            raise ChainIntegrityError("The existing chain was never anchored on Ethereum and fails verification, "
                                      "so it cannot be anchored. See \"Re-sealing an old chain\" in the README.")

        updates, head, length = plan_seal(rows)
        if not updates:
            if existing["anchor"] == "missing":
                Blockchain.anchor_chain(head, length)
            conn.rollback()
            return 0

        for update in updates:
            cursor.execute(
                "UPDATE TransactionDetails SET isBlockChainGenerated = 1, hash = ?, prevHash = ?, "
                "sequenceNumber = ? WHERE orderID = ?",
                (update["hash"], update["prevHash"], update["sequenceNumber"], update["orderID"]),
            )
        Blockchain.anchor_chain(head, length)
        conn.commit()
        return len(updates)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_chain():
    """Load every transaction, check the chain and its Ethereum anchor. Returns (blocks, summary)."""
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

    anchor = _read_anchor_or_error()
    summary = check_blocks(blocks, anchor)
    summary["anchorAddress"] = anchor.get("address")
    return blocks, summary
