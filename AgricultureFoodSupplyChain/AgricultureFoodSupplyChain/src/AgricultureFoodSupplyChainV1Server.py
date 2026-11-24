from functools import wraps
import os

from flask import Flask, request, render_template, redirect, url_for, session, g
import pyodbc

from Constants import connString

from AgricultureBoardModel import AgricultureBoardModel
from BuyerModel import BuyerModel
from FarmerModel import FarmerModel
from ProductModel import ProductModel
from RoleModel import RoleModel
from TransactionDetailsModel import TransactionDetailsModel
from UsersModel import UsersModel
import HashChain


app = Flask(__name__)
# Set FLASK_SECRET_KEY to keep sessions valid across restarts. Without it a
# random key is generated, so everyone is logged out when the server restarts.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


# ---------------------------------------------------------------------------
# Authentication and role-based access control
#
# The logged-in user's ID lives in the signed Flask session cookie, so every
# browser has its own login. The user and role are reloaded from the database
# on each request: deactivating a user or editing a role takes effect at once.
# ---------------------------------------------------------------------------

@app.before_request
def load_logged_in_user():
    g.user_id = None
    g.role = None
    if request.endpoint == "static":
        return
    user_id = session.get("user_id")
    if user_id is None:
        return
    conn = pyodbc.connect(connString, autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT u.userID, r.roleID, r.roleName, r.canRole, r.canUsers, r.canAgricultureBoard, r.canBuyer, "
            "r.canFarmer, r.canProduct, r.canTransactionDetails "
            "FROM Users u JOIN Role r ON r.roleID = u.roleID WHERE u.userID = ? AND u.isActive = 1",
            user_id,
        )
        row = cursor.fetchone()
    finally:
        conn.close()
    if row is None:
        session.clear()
        return
    g.user_id = row[0]
    g.role = RoleModel(*row[1:])


def show_info(message, msgType="Error"):
    session["info"] = (message, msgType)
    return redirect(url_for("Information"))


def login_required(permission=None, module=None):
    """Require a logged-in user, and optionally a role permission flag such as "canBuyer"."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.role is None:
                return redirect(url_for("index"))
            if permission and not getattr(g.role, permission):
                return show_info("You Don't Have Permission to Access " + module, "Error")
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.route("/")
def index():
    return render_template("Login.html")


@app.route("/processLogin", methods=["POST"])
def processLogin():
    emailid = request.form["emailid"]
    password = request.form["password"]
    conn1 = pyodbc.connect(connString, autocommit=True)
    try:
        cur1 = conn1.cursor()
        cur1.execute("SELECT userID, roleID FROM Users WHERE emailid = ? AND password = ? AND isActive = 1",
                     (emailid, password))
        row = cur1.fetchone()
        if not row:
            return render_template("Login.html", processResult="Invalid Credentials")
        cur1.execute("SELECT roleID FROM Role WHERE roleID = ?", row[1])
        if not cur1.fetchone():
            return render_template("Login.html", processResult="Invalid Role")
    finally:
        conn1.close()

    session.clear()
    session["user_id"] = row[0]
    return redirect(url_for("Dashboard"))


@app.route("/Logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/ChangePassword")
@login_required()
def changePassword():
    return render_template("ChangePassword.html")


@app.route("/ProcessChangePassword", methods=["POST"])
@login_required()
def processChangePassword():
    oldPassword = request.form["oldPassword"]
    newPassword = request.form["newPassword"]
    confirmPassword = request.form["confirmPassword"]
    conn1 = pyodbc.connect(connString, autocommit=True)
    try:
        cur1 = conn1.cursor()
        cur1.execute("SELECT userID FROM Users WHERE userID = ? AND password = ?", (g.user_id, oldPassword))
        if not cur1.fetchone():
            return render_template("ChangePassword.html", msg="Invalid Old Password")

        if newPassword.strip() != confirmPassword.strip():
            return render_template("ChangePassword.html", msg="New Password and Confirm Password are NOT same")

        cur1.execute("UPDATE Users SET password = ? WHERE userID = ?", (newPassword, g.user_id))
    finally:
        conn1.close()
    return render_template("ChangePassword.html", msg="Password Changed Successfully")


@app.route("/Dashboard")
@login_required()
def Dashboard():
    return render_template("Dashboard.html")


@app.route("/Information")
@login_required()
def Information():
    message, msgType = session.pop("info", ("", ""))
    return render_template("Information.html", msgType=msgType, message=message)


# ---------------------------------------------------------------------------
# Agriculture Board
# ---------------------------------------------------------------------------

@app.route("/AgricultureBoardListing")
@login_required("canAgricultureBoard", "AgricultureBoard")
def AgricultureBoard_listing():
    records = AgricultureBoardModel.get_all()
    return render_template("AgricultureBoardListing.html", records=records)


@app.route("/AgricultureBoardOperation")
@login_required("canAgricultureBoard", "AgricultureBoard")
def AgricultureBoard_operation():
    operation = request.args.get("operation")
    row = AgricultureBoardModel("", "")
    AgricultureBoard = AgricultureBoardModel.get_all()
    if operation != "Create":
        unique_id = request.args.get("unique_id").strip()
        row = AgricultureBoardModel.get_by_id(unique_id)
    return render_template("AgricultureBoardOperation.html", row=row, operation=operation, AgricultureBoard=AgricultureBoard)


@app.route("/ProcessAgricultureBoardOperation", methods=["POST"])
@login_required("canAgricultureBoard", "AgricultureBoard")
def process_AgricultureBoard_operation():
    operation = request.form["operation"]
    obj = AgricultureBoardModel("", "")

    if operation != "Delete":
        obj.agricultureBoardID = request.form['agricultureBoardID']
        obj.agricultureBoardName = request.form['agricultureBoardName']
        obj.contactNbr = request.form['contactNbr']
        obj.emailID = request.form['emailID']
        obj.address = request.form['address']
        obj.city = request.form['city']
        obj.county = request.form['county']
        obj.postcode = request.form['postcode']
        obj.country = request.form['country']

    if operation == "Create":
        obj.insert(obj)
    if operation == "Edit":
        obj.update(obj)
    if operation == "Delete":
        obj.delete(request.form["agricultureBoardID"])

    return redirect(url_for("AgricultureBoard_listing"))


# ---------------------------------------------------------------------------
# Buyer
# ---------------------------------------------------------------------------

@app.route("/BuyerListing")
@login_required("canBuyer", "Buyer")
def Buyer_listing():
    records = BuyerModel.get_all()
    return render_template("BuyerListing.html", records=records)


@app.route("/BuyerOperation")
@login_required("canBuyer", "Buyer")
def Buyer_operation():
    operation = request.args.get("operation")
    row = BuyerModel("", "")
    Buyer = BuyerModel.get_all()
    if operation != "Create":
        unique_id = request.args.get("unique_id").strip()
        row = BuyerModel.get_by_id(unique_id)
    return render_template("BuyerOperation.html", row=row, operation=operation, Buyer=Buyer)


@app.route("/ProcessBuyerOperation", methods=["POST"])
@login_required("canBuyer", "Buyer")
def process_Buyer_operation():
    operation = request.form["operation"]
    obj = BuyerModel("", "")

    if operation != "Delete":
        obj.buyerID = request.form['buyerID']
        obj.buyerName = request.form['buyerName']
        obj.contactNbr = request.form['contactNbr']
        obj.emailID = request.form['emailID']
        obj.address = request.form['address']
        obj.city = request.form['city']
        obj.county = request.form['county']
        obj.postcode = request.form['postcode']
        obj.country = request.form['country']
        obj.inbusiness = request.form['inbusiness']
        obj.adharNumber = request.form['adharNumber']

    if operation == "Create":
        obj.insert(obj)
    if operation == "Edit":
        obj.update(obj)
    if operation == "Delete":
        obj.delete(request.form["buyerID"])

    return redirect(url_for("Buyer_listing"))


# ---------------------------------------------------------------------------
# Farmer
# ---------------------------------------------------------------------------

@app.route("/FarmerListing")
@login_required("canFarmer", "Farmer")
def Farmer_listing():
    records = FarmerModel.get_all()
    return render_template("FarmerListing.html", records=records)


@app.route("/FarmerOperation")
@login_required("canFarmer", "Farmer")
def Farmer_operation():
    operation = request.args.get("operation")
    row = FarmerModel("", "")
    Farmer = FarmerModel.get_all()
    if operation != "Create":
        unique_id = request.args.get("unique_id").strip()
        row = FarmerModel.get_by_id(unique_id)
    return render_template("FarmerOperation.html", row=row, operation=operation, Farmer=Farmer)


@app.route("/ProcessFarmerOperation", methods=["POST"])
@login_required("canFarmer", "Farmer")
def process_Farmer_operation():
    operation = request.form["operation"]
    obj = FarmerModel("", "")

    if operation != "Delete":
        obj.farmerID = request.form['farmerID']
        obj.farmerName = request.form['farmerName']
        obj.contactNbr = request.form['contactNbr']
        obj.emailID = request.form['emailID']
        obj.address = request.form['address']
        obj.city = request.form['city']
        obj.county = request.form['county']
        obj.postcode = request.form['postcode']
        obj.country = request.form['country']
        obj.adharNumber = request.form['adharNumber']

    if operation == "Create":
        obj.insert(obj)
    if operation == "Edit":
        obj.update(obj)
    if operation == "Delete":
        obj.delete(request.form["farmerID"])

    return redirect(url_for("Farmer_listing"))


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

@app.route("/ProductListing")
@login_required("canProduct", "Product")
def Product_listing():
    records = ProductModel.get_all()
    return render_template("ProductListing.html", records=records)


@app.route("/ProductOperation")
@login_required("canProduct", "Product")
def Product_operation():
    operation = request.args.get("operation")
    row = ProductModel("", "")
    Product = ProductModel.get_all()
    if operation != "Create":
        unique_id = request.args.get("unique_id").strip()
        row = ProductModel.get_by_id(unique_id)
    return render_template("ProductOperation.html", row=row, operation=operation, Product=Product)


@app.route("/ProcessProductOperation", methods=["POST"])
@login_required("canProduct", "Product")
def process_Product_operation():
    operation = request.form["operation"]
    obj = ProductModel("", "")

    if operation != "Delete":
        obj.productID = request.form['productID']
        obj.productName = request.form['productName']
        obj.packageSize = request.form['packageSize']
        obj.price = request.form['price']

    if operation == "Create":
        obj.insert(obj)
    if operation == "Edit":
        obj.update(obj)
    if operation == "Delete":
        obj.delete(request.form["productID"])

    return redirect(url_for("Product_listing"))


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------

@app.route("/RoleListing")
@login_required("canRole", "Role")
def Role_listing():
    records = RoleModel.get_all()
    return render_template("RoleListing.html", records=records)


@app.route("/RoleOperation")
@login_required("canRole", "Role")
def Role_operation():
    operation = request.args.get("operation")
    row = RoleModel("", "")
    Role = RoleModel.get_all()
    if operation != "Create":
        unique_id = request.args.get("unique_id").strip()
        row = RoleModel.get_by_id(unique_id)
    return render_template("RoleOperation.html", row=row, operation=operation, Role=Role)


@app.route("/ProcessRoleOperation", methods=["POST"])
@login_required("canRole", "Role")
def process_Role_operation():
    operation = request.form["operation"]
    obj = RoleModel("", "")

    if operation != "Delete":
        obj.roleID = request.form['roleID']
        obj.roleName = request.form['roleName']
        for flag in ("canRole", "canUsers", "canAgricultureBoard", "canBuyer",
                     "canFarmer", "canProduct", "canTransactionDetails"):
            setattr(obj, flag, 1 if request.form.get(flag) is not None else 0)

    if operation == "Create":
        obj.insert(obj)
    if operation == "Edit":
        obj.update(obj)
    if operation == "Delete":
        obj.delete(request.form["roleID"])

    return redirect(url_for("Role_listing"))


# ---------------------------------------------------------------------------
# Transaction Details
# ---------------------------------------------------------------------------

@app.route("/TransactionDetailsListing")
@login_required("canTransactionDetails", "TransactionDetails")
def TransactionDetails_listing():
    records = TransactionDetailsModel.get_all()
    return render_template("TransactionDetailsListing.html", records=records)


@app.route("/TransactionDetailsOperation")
@login_required("canTransactionDetails", "TransactionDetails")
def TransactionDetails_operation():
    operation = request.args.get("operation")
    row = TransactionDetailsModel("", "")
    TransactionDetails = TransactionDetailsModel.get_all()
    agricultureBoard_list = AgricultureBoardModel.get_name_id()
    buyer_list = BuyerModel.get_name_id()
    farmer_list = FarmerModel.get_name_id()
    product_list = ProductModel.get_name_id()
    if operation != "Create":
        unique_id = request.args.get("unique_id").strip()
        row = TransactionDetailsModel.get_by_id(unique_id)

    return render_template("TransactionDetailsOperation.html", row=row, operation=operation,
                           TransactionDetails=TransactionDetails, agricultureBoard_list=agricultureBoard_list,
                           buyer_list=buyer_list, farmer_list=farmer_list, product_list=product_list)


@app.route("/ProcessTransactionDetailsOperation", methods=["POST"])
@login_required("canTransactionDetails", "TransactionDetails")
def process_TransactionDetails_operation():
    operation = request.form["operation"]
    obj = TransactionDetailsModel("", "")

    if operation != "Delete":
        obj.orderID = request.form['orderID']
        obj.agricultureBoardID = request.form['agricultureBoardID']
        obj.gstNbr = request.form['gstNbr']
        obj.buyerID = request.form['buyerID']
        obj.farmerID = request.form['farmerID']
        obj.effDate = request.form['effDate']
        obj.productID = request.form['productID']
        obj.price = request.form['price']
        obj.qty = request.form['qty']

    if operation == "Create":
        obj.insert(obj)
    if operation == "Edit":
        obj.update(obj)
    if operation == "Delete":
        obj.delete(request.form["orderID"])

    return redirect(url_for("TransactionDetails_listing"))


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.route("/UsersListing")
@login_required("canUsers", "Users")
def Users_listing():
    records = UsersModel.get_all()
    return render_template("UsersListing.html", records=records)


@app.route("/UsersOperation")
@login_required("canUsers", "Users")
def Users_operation():
    operation = request.args.get("operation")
    row = UsersModel("", "")
    Users = UsersModel.get_all()
    role_list = RoleModel.get_name_id()
    if operation != "Create":
        unique_id = request.args.get("unique_id").strip()
        row = UsersModel.get_by_id(unique_id)
    return render_template("UsersOperation.html", row=row, operation=operation, Users=Users, role_list=role_list)


@app.route("/ProcessUsersOperation", methods=["POST"])
@login_required("canUsers", "Users")
def process_Users_operation():
    operation = request.form["operation"]
    obj = UsersModel("", "")

    if operation != "Delete":
        obj.userID = request.form['userID']
        obj.userName = request.form['userName']
        obj.emailid = request.form['emailid']
        obj.password = request.form['password']
        obj.contactNo = request.form['contactNo']
        obj.isActive = 1 if request.form.get("isActive") is not None else 0
        obj.roleID = request.form['roleID']

    if operation == "Create":
        obj.insert(obj)
    if operation == "Edit":
        obj.update(obj)
    if operation == "Delete":
        obj.delete(request.form["userID"])

    return redirect(url_for("Users_listing"))


# ---------------------------------------------------------------------------
# Hash chain (see HashChain.py)
# ---------------------------------------------------------------------------

@app.route("/BlockChainGeneration")
@login_required("canTransactionDetails", "Blockchain")
def BlockChainGeneration():
    blocksCreated, blocksNotCreated = HashChain.count_blocks()
    return render_template('BlockChainGeneration.html', blocksCreated=blocksCreated, blocksNotCreated=blocksNotCreated)


@app.route("/ProcessBlockchainGeneration", methods=['POST'])
@login_required("canTransactionDetails", "Blockchain")
def ProcessBlockchainGeneration():
    blocksSealed = HashChain.seal_pending_blocks()
    return render_template('BlockchainGenerationResult.html', blocksSealed=blocksSealed)


@app.route("/BlockChainReport")
@login_required("canTransactionDetails", "Blockchain")
def BlockChainReport():
    blocks, summary = HashChain.verify_chain()
    return render_template('BlockChainReport.html', blocks=blocks, summary=summary)


if __name__ == "__main__":
    app.run(host=os.environ.get("FLASK_RUN_HOST", "127.0.0.1"), port=int(os.environ.get("FLASK_RUN_PORT", "5000")))
