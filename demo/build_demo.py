"""Build the read-only Vercel demo: the app's real templates rendered with sample data.

    python demo/build_demo.py            # writes demo/dist/

Vercel cannot host SQL Server or Ganache, so the demo has no backend. Every
page is pre-rendered from the same Jinja templates the Flask app uses. The
Blockchain Report is computed with the app's real HashChain functions, once for
an intact chain and once with a sealed record edited. Forms are disabled, and a
banner points to the Docker setup for the full app.

Needs only Jinja2 (pip install jinja2).
"""
import datetime
import os
import shutil
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "AgricultureFoodSupplyChain", "AgricultureFoodSupplyChain", "src")
OUT = os.path.join(ROOT, "demo", "dist")
REPO_URL = "https://github.com/MadhavVN011/AgroTrustChain"

# HashChain imports the database driver and the Ethereum module at import time.
# The demo only uses its pure functions, so stand-ins are enough.
sys.modules.setdefault("pyodbc", types.ModuleType("pyodbc"))
sys.modules.setdefault("Blockchain", types.ModuleType("Blockchain"))
sys.path.insert(0, SRC)
import HashChain  # noqa: E402

from jinja2 import Environment, FileSystemLoader  # noqa: E402

# ---------------------------------------------------------------------------
# Sample data (fictional)
# ---------------------------------------------------------------------------

BOARDS = [
    {"agricultureBoardID": "AB-001", "agricultureBoardName": "Western Ghats Agriculture Board", "contactNbr": "0484-200100",
     "emailID": "board@example.org", "address": "12 Market Road", "city": "Kochi", "county": "Ernakulam", "postcode": "682001", "country": "India"},
    {"agricultureBoardID": "AB-002", "agricultureBoardName": "Deccan Produce Board", "contactNbr": "040-300200",
     "emailID": "deccan@example.org", "address": "4 Mandi Lane", "city": "Hyderabad", "county": "Hyderabad", "postcode": "500001", "country": "India"},
]
FARMERS = [
    {"farmerID": "F-101", "farmerName": "Green Valley Farms", "contactNbr": "98000 00101", "emailID": "greenvalley@example.org",
     "address": "Plot 7", "city": "Thrissur", "county": "Thrissur", "postcode": "680001", "country": "India", "adharNumber": "XXXX-XXXX-0101"},
    {"farmerID": "F-102", "farmerName": "Sunrise Organics", "contactNbr": "98000 00102", "emailID": "sunrise@example.org",
     "address": "Plot 22", "city": "Nashik", "county": "Nashik", "postcode": "422001", "country": "India", "adharNumber": "XXXX-XXXX-0102"},
]
BUYERS = [
    {"buyerID": "B-201", "buyerName": "FreshCart Distributors", "contactNbr": "98000 00201", "emailID": "freshcart@example.org",
     "address": "Warehouse 3", "city": "Bengaluru", "county": "Bengaluru Urban", "postcode": "560001", "country": "India",
     "inbusiness": 1, "adharNumber": "XXXX-XXXX-0201"},
    {"buyerID": "B-202", "buyerName": "City Grocers Co-op", "contactNbr": "98000 00202", "emailID": "citygrocers@example.org",
     "address": "Shop 9", "city": "Chennai", "county": "Chennai", "postcode": "600001", "country": "India",
     "inbusiness": 1, "adharNumber": "XXXX-XXXX-0202"},
]
PRODUCTS = [
    {"productID": "P-301", "productName": "Basmati Rice", "packageSize": "25 kg", "price": 1800.0},
    {"productID": "P-302", "productName": "Alphonso Mangoes", "packageSize": "5 kg", "price": 950.0},
    {"productID": "P-303", "productName": "Black Pepper", "packageSize": "1 kg", "price": 640.0},
]
ROLES = [
    {"roleID": 1, "roleName": "Administrator", "canRole": True, "canUsers": True, "canAgricultureBoard": True,
     "canBuyer": True, "canFarmer": True, "canProduct": True, "canTransactionDetails": True},
    {"roleID": 2, "roleName": "Auditor", "canRole": False, "canUsers": False, "canAgricultureBoard": False,
     "canBuyer": False, "canFarmer": False, "canProduct": False, "canTransactionDetails": True},
]
USERS = [
    {"userID": 1, "userName": "Demo Admin", "emailid": "admin@example.org", "contactNo": "98000 00001", "isActive": True, "roleID": 1},
    {"userID": 2, "userName": "Demo Auditor", "emailid": "auditor@example.org", "contactNo": "98000 00002", "isActive": True, "roleID": 2},
]

# (board, farmer, buyer, product, qty, date)
_TRANSACTIONS = [
    (0, 0, 0, 0, 40, datetime.date(2026, 3, 2)),
    (0, 0, 1, 1, 120, datetime.date(2026, 3, 9)),
    (1, 1, 0, 2, 75, datetime.date(2026, 3, 16)),
    (1, 1, 1, 0, 60, datetime.date(2026, 3, 23)),
    (0, 0, 0, 2, 30, datetime.date(2026, 3, 30)),
    (1, 1, 1, 1, 90, datetime.date(2026, 4, 6)),
]


def transaction_rows():
    rows = []
    for n, (b, f, by, p, qty, date) in enumerate(_TRANSACTIONS, start=1):
        rows.append({
            "orderID": "ORD-2026-%04d" % n,
            "agricultureBoardID": BOARDS[b]["agricultureBoardID"], "agricultureBoardName": BOARDS[b]["agricultureBoardName"],
            "gstNbr": "32ABCDE%04dF1Z5" % n,
            "buyerID": BUYERS[by]["buyerID"], "buyerName": BUYERS[by]["buyerName"],
            "farmerID": FARMERS[f]["farmerID"], "farmerName": FARMERS[f]["farmerName"],
            "effDate": date,
            "productID": PRODUCTS[p]["productID"], "productName": PRODUCTS[p]["productName"],
            "price": PRODUCTS[p]["price"] * qty / 10, "qty": float(qty),
            "isBlockChainGenerated": False, "hash": "", "prevHash": "", "sequenceNumber": n, "ethTxHash": None,
        })
    return rows


def sealed_chain():
    """All but the newest transaction sealed with the app's own HashChain.plan_seal."""
    rows = transaction_rows()
    updates, head, length = HashChain.plan_seal(rows[:-1])
    by_id = {u["orderID"]: u for u in updates}
    for row in rows[:-1]:
        row.update(by_id[row["orderID"]], isBlockChainGenerated=True)
    return rows, {"head": head, "length": length}


def report(tamper):
    blocks, anchor = sealed_chain()
    if tamper:
        blocks[2]["price"] = 1.0  # a sealed record edited after the fact
    summary = HashChain.check_blocks(blocks, anchor)
    summary["anchorAddress"] = "(not deployed in this demo)"
    return blocks, summary


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

BANNER = """
<div id="demo-banner" style="position:sticky;top:0;z-index:1000;background:#fff3cd;color:#664d03;border-bottom:1px solid #ffe69c;
     padding:.6rem 1rem;font:14px/1.4 system-ui,sans-serif;text-align:center">
  <b>Read-only demo with sample data.</b> Nothing is saved, and there is no database or Ethereum node behind this page.
  The Blockchain Report is computed with the app's real verification code:
  <a href="/BlockChainReport">intact chain</a> &middot; <a href="/BlockChainReportTampered">tampered example</a>.
  To run the full app, see <a href="REPO_URL#setup-with-docker">Setup with Docker</a>.
</div>
""".replace("REPO_URL", REPO_URL)

SCRIPT = """
<script>
document.querySelectorAll('form').forEach(function (form) {
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (form.getAttribute('action') === '/processLogin') { window.location.href = '/Dashboard'; return; }
    alert('This is a read-only demo, so changes are not saved. Run the full app with Docker to try it for real.');
  });
});
</script>
"""


def inject(html):
    html = html.replace("<body>", "<body>" + BANNER, 1)
    return html.replace("</body>", SCRIPT + "</body>", 1)


def main():
    env = Environment(loader=FileSystemLoader(os.path.join(SRC, "templates")), autoescape=True)
    env.globals["csrf_token"] = lambda: "demo"

    # Start clean, but keep .vercel/ (the local `vercel link` of this folder).
    if os.path.exists(OUT):
        for entry in os.listdir(OUT):
            if entry != ".vercel":
                path = os.path.join(OUT, entry)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    shutil.copytree(os.path.join(SRC, "static"), os.path.join(OUT, "static"),
                    ignore=shutil.ignore_patterns(".gitkeep", "UPLOADED_FILES", "charts"))

    transactions = transaction_rows()
    intact_blocks, intact_summary = report(tamper=False)
    tampered_blocks, tampered_summary = report(tamper=True)
    sealed = sum(1 for b in intact_blocks if b["isBlockChainGenerated"])
    create = {"operation": "Create", "row": {}}

    pages = {
        "index": ("Login.html", {}),
        "Dashboard": ("Dashboard.html", {}),
        "ChangePassword": ("ChangePassword.html", {"msg": ""}),
        "AgricultureBoardListing": ("AgricultureBoardListing.html", {"records": BOARDS}),
        "AgricultureBoardOperation": ("AgricultureBoardOperation.html", create),
        "FarmerListing": ("FarmerListing.html", {"records": FARMERS}),
        "FarmerOperation": ("FarmerOperation.html", create),
        "BuyerListing": ("BuyerListing.html", {"records": BUYERS}),
        "BuyerOperation": ("BuyerOperation.html", create),
        "ProductListing": ("ProductListing.html", {"records": PRODUCTS}),
        "ProductOperation": ("ProductOperation.html", create),
        "RoleListing": ("RoleListing.html", {"records": ROLES}),
        "RoleOperation": ("RoleOperation.html", create),
        "UsersListing": ("UsersListing.html", {"records": USERS}),
        "UsersOperation": ("UsersOperation.html", dict(create, role_list=ROLES)),
        "TransactionDetailsListing": ("TransactionDetailsListing.html", {"records": transactions}),
        "TransactionDetailsOperation": ("TransactionDetailsOperation.html", dict(
            create, agricultureBoard_list=BOARDS, buyer_list=BUYERS, farmer_list=FARMERS, product_list=PRODUCTS)),
        "BlockChainGeneration": ("BlockChainGeneration.html",
                                 {"blocksCreated": sealed, "blocksNotCreated": len(intact_blocks) - sealed}),
        "BlockChainReport": ("BlockChainReport.html", {"blocks": intact_blocks, "summary": intact_summary}),
        "BlockChainReportTampered": ("BlockChainReport.html", {"blocks": tampered_blocks, "summary": tampered_summary}),
    }
    for name, (template, context) in pages.items():
        html = inject(env.get_template(template).render(**context))
        with open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8") as file:
            file.write(html)

    # Logout returns to the login page.
    with open(os.path.join(OUT, "Logout.html"), "w", encoding="utf-8") as file:
        file.write('<!DOCTYPE html><meta http-equiv="refresh" content="0; url=/"><a href="/">Back to login</a>')

    shutil.copy(os.path.join(ROOT, "demo", "vercel.json"), os.path.join(OUT, "vercel.json"))

    assert intact_summary["intact"] and not tampered_summary["intact"], "demo chain did not verify as expected"
    print("Built %d pages into %s (intact chain: %s, tampered example: %d block(s) flagged)"
          % (len(pages) + 1, OUT, intact_summary["intact"], tampered_summary["tampered"]))


if __name__ == "__main__":
    main()
