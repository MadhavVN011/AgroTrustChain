"""Product batches (table Batch). Scores and penalties are on-chain; see Blockchain.py."""
import pyodbc

from Constants import connString

_SELECT = (
    "SELECT b.batchID, b.farmerID, f.farmerName, b.productID, p.productName, b.certificateNumber, "
    "b.certificateHash, b.certificateExpiry, b.claimedQuality, b.inspectedQuality, b.status, "
    "b.ethTxHash, b.inspectionTxHash, b.createdAt "
    "FROM Batch b LEFT JOIN Farmer f ON f.farmerID = b.farmerID LEFT JOIN Product p ON p.productID = b.productID "
)


def _dicts(cursor):
    names = [col[0] for col in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def get_all():
    conn = pyodbc.connect(connString, autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute(_SELECT + "ORDER BY b.createdAt DESC")
        return _dicts(cursor)
    finally:
        conn.close()


def get_by_id(batch_id):
    conn = pyodbc.connect(connString, autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute(_SELECT + "WHERE b.batchID = ?", batch_id)
        rows = _dicts(cursor)
        return rows[0] if rows else None
    finally:
        conn.close()


def insert(batch):
    conn = pyodbc.connect(connString, autocommit=True)
    try:
        conn.cursor().execute(
            "INSERT INTO Batch (batchID, farmerID, productID, certificateNumber, certificateHash, certificateExpiry, "
            "claimedQuality, status, ethTxHash) VALUES (?,?,?,?,?,?,?,?,?)",
            (batch["batchID"], batch["farmerID"], batch["productID"] or None, batch["certificateNumber"],
             batch["certificateHash"], batch["certificateExpiry"], batch["claimedQuality"], "Pending", batch["ethTxHash"]))
    finally:
        conn.close()


def record_inspection(batch_id, inspected_quality, status, tx_hash):
    conn = pyodbc.connect(connString, autocommit=True)
    try:
        conn.cursor().execute(
            "UPDATE Batch SET inspectedQuality = ?, status = ?, inspectionTxHash = ? WHERE batchID = ?",
            (inspected_quality, status, tx_hash, batch_id))
    finally:
        conn.close()


def mark_certificate_revoked(certificate_hash):
    conn = pyodbc.connect(connString, autocommit=True)
    try:
        conn.cursor().execute(
            "UPDATE Batch SET status = 'Certificate revoked' WHERE certificateHash = ? AND status <> 'Revoked'",
            certificate_hash)
    finally:
        conn.close()
