from Constants import connString
import pyodbc
import datetime
import uuid
import time
import Blockchain


class TransactionDetailsModel:
    def __init__(self, orderID = '',agricultureBoardID = '',gstNbr = '',buyerID = '',farmerID = '',effDate = None,productID = '',price = 0,qty = 0,isBlockChainGenerated = False,hash = '',prevHash = '',sequenceNumber = 0,agricultureBoardModel = None,buyerModel = None,farmerModel = None,productModel = None):
        self.orderID = orderID
        self.agricultureBoardID = agricultureBoardID
        self.gstNbr = gstNbr
        self.buyerID = buyerID
        self.farmerID = farmerID
        self.effDate = effDate
        self.productID = productID
        self.price = price
        self.qty = qty
        self.isBlockChainGenerated = isBlockChainGenerated
        self.hash = hash
        self.prevHash = prevHash
        self.sequenceNumber = sequenceNumber
        self.agricultureBoardModel = agricultureBoardModel
        self.buyerModel = buyerModel
        self.farmerModel = farmerModel
        self.productModel = productModel
       
        

    @staticmethod
    def get_all():
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "SELECT * FROM TransactionDetails ORDER BY farmerID"
        cursor.execute(sqlcmd1)
        records = []
        for dbrow in cursor.fetchall():
            row = TransactionDetailsModel(dbrow[0],dbrow[1],dbrow[2],dbrow[3],dbrow[4],dbrow[5],dbrow[6],dbrow[7],dbrow[8],dbrow[9],dbrow[10],dbrow[11],dbrow[12])
            records.append(row)
        cursor.close()
        conn.close()
        return records

    @staticmethod
    def get_listing(limit=None):
        """Transactions with participant and product names, newest first, as dicts."""
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        top = "TOP (%d) " % int(limit) if limit else ""
        cursor.execute(
            "SELECT " + top + "td.orderID, td.effDate, td.gstNbr, td.price, td.qty, td.isBlockChainGenerated, td.sequenceNumber, "
            "td.ethTxHash, ab.agricultureBoardName, f.farmerName, b.buyerName, p.productName "
            "FROM TransactionDetails td "
            "LEFT JOIN AgricultureBoard ab ON ab.agricultureBoardID = td.agricultureBoardID "
            "LEFT JOIN Farmer f ON f.farmerID = td.farmerID "
            "LEFT JOIN Buyer b ON b.buyerID = td.buyerID "
            "LEFT JOIN Product p ON p.productID = td.productID "
            "ORDER BY td.sequenceNumber DESC")
        names = [col[0] for col in cursor.description]
        records = [dict(zip(names, row)) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return records

    @staticmethod
    def get_name_id():
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "SELECT orderID, farmerID FROM TransactionDetails  ORDER BY farmerID"
        cursor.execute(sqlcmd1)
        records = []
        for dbrow in cursor.fetchall():
            row = TransactionDetailsModel(dbrow[0],dbrow[1])
            records.append(row)
        cursor.close()
        conn.close()
        return records
        
    @staticmethod
    def get_by_id(unique_id):
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "SELECT * FROM TransactionDetails WHERE orderID = ?"
        cursor.execute(sqlcmd1, unique_id)
        record = None
        for dbrow in cursor.fetchall():
            record = TransactionDetailsModel(dbrow[0],dbrow[1],dbrow[2],dbrow[3],dbrow[4],dbrow[5],dbrow[6],dbrow[7],dbrow[8],dbrow[9],dbrow[10],dbrow[11],dbrow[12])
        cursor.close()
        conn.close()
        return record
    
    @staticmethod
    def insert(obj):
        """Record the transaction on Ethereum first, then store it with its Ethereum tx hash.

        Writing to the chain first means a database row always has an on-chain
        record: if Ethereum is unreachable, nothing is stored and
        Blockchain.BlockchainError is raised.
        """
        obj.orderID = str(uuid.uuid4())
        effDate = datetime.datetime.strptime(obj.effDate.replace('T', ' '), '%Y-%m-%d')
        price = float(obj.price)
        qty = float(obj.qty)

        obj.ethTxHash = Blockchain.record_transaction(obj.agricultureBoardID, obj.buyerID, obj.farmerID, obj.productID, price, qty)

        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        # New transactions start unsealed and take the next sequenceNumber. The
        # UPDLOCK/HOLDLOCK hint makes MAX()+1 safe against concurrent inserts.
        sqlcmd1 = ("INSERT INTO TransactionDetails (orderID,agricultureBoardID,gstNbr,buyerID,farmerID,effDate,productID,price,qty,isBlockChainGenerated,hash,prevHash,sequenceNumber,ethTxHash) "
                   "SELECT ?,?,?,?,?,?,?,?,?,0,'','',ISNULL(MAX(sequenceNumber), 0) + 1,? FROM TransactionDetails WITH (UPDLOCK, HOLDLOCK)")
        cursor.execute(sqlcmd1, (obj.orderID,obj.agricultureBoardID,obj.gstNbr,obj.buyerID,obj.farmerID,effDate,obj.productID,price,qty,obj.ethTxHash))
        cursor.close()
        conn.close()

    @staticmethod
    def update(obj):
        # Only business fields are updated. The seal columns (isBlockChainGenerated,
        # hash, prevHash, sequenceNumber) are owned by HashChain: editing a sealed
        # transaction keeps its stored hash, so the Blockchain Report flags the edit.
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "UPDATE TransactionDetails SET agricultureBoardID = ?,gstNbr = ?,buyerID = ?,farmerID = ?,effDate = ?,productID = ?,price = ?,qty = ? WHERE orderID = ?"
        cursor.execute(sqlcmd1,  (obj.agricultureBoardID,obj.gstNbr,obj.buyerID,obj.farmerID,datetime.datetime.strptime(obj.effDate.replace('T', ' '), '%Y-%m-%d'),obj.productID,obj.price,obj.qty,obj.orderID))
        cursor.close()
        conn.close()

    @staticmethod
    def delete(unique_id):
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "DELETE FROM TransactionDetails WHERE orderID = ?"
        cursor.execute(sqlcmd1, (unique_id))
        cursor.close()
        conn.close()

