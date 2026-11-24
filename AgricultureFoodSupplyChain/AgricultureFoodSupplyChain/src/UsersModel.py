from Constants import connString
import pyodbc
import datetime
import uuid
import time
import Constants    
import Passwords

class UsersModel:
    def __init__(self, userID = 0,userName = '',emailid = '',password = '',contactNo = '',isActive = False,roleID = 0,roleModel = None):
        self.userID = userID
        self.userName = userName
        self.emailid = emailid
        self.password = password
        self.contactNo = contactNo
        self.isActive = isActive
        self.roleID = roleID
        self.roleModel = roleModel
       
        

    @staticmethod
    def get_all():
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "SELECT * FROM Users ORDER BY userName"
        cursor.execute(sqlcmd1)
        records = []
        for dbrow in cursor.fetchall():
            row = UsersModel(dbrow[0],dbrow[1],dbrow[2],dbrow[3],dbrow[4],dbrow[5],dbrow[6])
            records.append(row)
        cursor.close()
        conn.close()
        return records

    @staticmethod
    def get_name_id():
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "SELECT userID, userName FROM Users  WHERE isActive = 1  ORDER BY userName"
        cursor.execute(sqlcmd1)
        records = []
        for dbrow in cursor.fetchall():
            row = UsersModel(dbrow[0],dbrow[1])
            records.append(row)
        cursor.close()
        conn.close()
        return records
        
    @staticmethod
    def get_by_id(unique_id):
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "SELECT * FROM Users WHERE userID = ?"
        cursor.execute(sqlcmd1, unique_id)
        record = None
        for dbrow in cursor.fetchall():
            record = UsersModel(dbrow[0],dbrow[1],dbrow[2],dbrow[3],dbrow[4],dbrow[5],dbrow[6])
        cursor.close()
        conn.close()
        return record
    
    @staticmethod
    def insert(obj):
        obj.userID = str(uuid.uuid4())
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "INSERT INTO Users (userName,emailid,password,contactNo,isActive,roleID) VALUES(?,?,?,?,?,?)"
        cursor.execute(sqlcmd1, (obj.userName,obj.emailid,Passwords.hash_password(obj.password),obj.contactNo,obj.isActive,obj.roleID))
        cursor.close()
        conn.close()
        
    
    @staticmethod
    def update(obj):
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        if obj.password:
            sqlcmd1 = "UPDATE Users SET userName = ?,emailid = ?,password = ?,contactNo = ?,isActive = ?,roleID = ? WHERE userID = ?"
            cursor.execute(sqlcmd1,  (obj.userName,obj.emailid,Passwords.hash_password(obj.password),obj.contactNo,obj.isActive,obj.roleID,obj.userID))
        else:
            # A blank password on the edit form keeps the current one.
            sqlcmd1 = "UPDATE Users SET userName = ?,emailid = ?,contactNo = ?,isActive = ?,roleID = ? WHERE userID = ?"
            cursor.execute(sqlcmd1,  (obj.userName,obj.emailid,obj.contactNo,obj.isActive,obj.roleID,obj.userID))
        cursor.close()
        conn.close()
    
    @staticmethod
    def set_password(user_id, password):
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        cursor.execute("UPDATE Users SET password = ? WHERE userID = ?", (Passwords.hash_password(password), user_id))
        cursor.close()
        conn.close()

    @staticmethod
    def hash_plaintext_passwords():
        """Replace any legacy plain-text passwords with hashes. Returns how many were upgraded."""
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        cursor.execute("SELECT userID, password FROM Users")
        legacy = [(row[0], row[1]) for row in cursor.fetchall() if row[1] and not Passwords.is_hashed(row[1])]
        for user_id, password in legacy:
            cursor.execute("UPDATE Users SET password = ? WHERE userID = ? AND password = ?",
                           (Passwords.hash_password(password), user_id, password))
        cursor.close()
        conn.close()
        return len(legacy)

    @staticmethod
    def delete(unique_id):
        conn = pyodbc.connect(connString, autocommit=True)
        cursor = conn.cursor()
        sqlcmd1 = "DELETE FROM Users WHERE userID = ?"
        cursor.execute(sqlcmd1, (unique_id))
        cursor.close()
        conn.close()

