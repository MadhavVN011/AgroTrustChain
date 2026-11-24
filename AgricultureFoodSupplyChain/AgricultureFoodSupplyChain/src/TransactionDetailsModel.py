from Constants import connString
import pyodbc
import datetime
import uuid
import time
import os
import Constants
from web3 import Web3, HTTPProvider
import json


def _load_transaction_contract(w3):
    """Return the deployed TransactionDetailsContract for the network Ganache is on."""
    artifact_path = os.path.join(Constants.contracts_build_dir, "TransactionDetailsContract.json")
    with open(artifact_path) as file:
        artifact = json.load(file)

    address = Constants.contract_address
    if not address:
        network_id = str(w3.net.version)
        address = artifact.get("networks", {}).get(network_id, {}).get("address")
        if not address:
            raise RuntimeError(
                "TransactionDetailsContract is not deployed on Ethereum network " + network_id
                + ". Run `truffle migrate` against this network, or set CONTRACT_ADDRESS."
            )
    to_checksum = getattr(Web3, "to_checksum_address", None) or Web3.toChecksumAddress
    return w3.eth.contract(address=to_checksum(address), abi=artifact["abi"])
        
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
        obj.orderID = str(uuid.uuid4())
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        # New transactions start unsealed and take the next sequenceNumber. The
        # UPDLOCK/HOLDLOCK hint makes MAX()+1 safe against concurrent inserts.
        sqlcmd1 = ("INSERT INTO TransactionDetails (orderID,agricultureBoardID,gstNbr,buyerID,farmerID,effDate,productID,price,qty,isBlockChainGenerated,hash,prevHash,sequenceNumber) "
                   "SELECT ?,?,?,?,?,?,?,?,?,0,'','',ISNULL(MAX(sequenceNumber), 0) + 1 FROM TransactionDetails WITH (UPDLOCK, HOLDLOCK)")
        cursor.execute(sqlcmd1, (obj.orderID,obj.agricultureBoardID,obj.gstNbr,obj.buyerID,obj.farmerID,datetime.datetime.strptime(obj.effDate.replace('T', ' '), '%Y-%m-%d'),obj.productID,obj.price,obj.qty))
        cursor.close()
        conn.close()

        w3 = Web3(HTTPProvider(Constants.eth_rpc_url))
        contract = _load_transaction_contract(w3)
        accounts = w3.eth.accounts

        tx_hash = contract.functions.perform_transactions(str(obj.agricultureBoardID), str(obj.buyerID), str(obj.farmerID), str(obj.productID), int(float(obj.price)), int(float(obj.qty))).transact({'from': accounts[0]})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

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

