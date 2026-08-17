# AgroTrustChain — Blockchain-Based Agricultural Food Supply Chain Traceability

A blockchain-enabled traceability system for the agri-food supply chain, built as a Flask web
application backed by SQL Server for operational records and a private Ethereum network (Ganache
+ Truffle + Solidity) for tamper-evident transaction anchoring.

Every purchase transaction between a farmer, a buyer, and an agriculture board is written to a
relational database, mirrored onto an Ethereum smart contract through Web3.py, and chained into a
SHA-256 hash ledger (`hash` / `prevHash`) that can be audited from a web report.

Created by **Madhav Nair**, **Ishaan Chaturvedi**, and **Kunal Saha**.

This repository is the implementation companion to the research paper *"Enhancing and Securing
Agricultural Products Traceability Using Ethereum Based AgroTrustChain Framework"*.

---

## Table of Contents

1. [Motivation](#motivation)
2. [What the System Does](#what-the-system-does)
3. [Architecture](#architecture)
4. [Repository Layout](#repository-layout)
5. [Technology Stack](#technology-stack)
6. [Data Model](#data-model)
7. [Smart Contracts](#smart-contracts)
8. [The Hash Chain (Block Generation)](#the-hash-chain-block-generation)
9. [Role-Based Access Control](#role-based-access-control)
10. [Application Routes](#application-routes)
11. [Setup and Installation](#setup-and-installation)
12. [Running the Project](#running-the-project)
13. [Typical Workflow](#typical-workflow)
14. [Research Context: WTH-Raft and the AgroTrustChain Framework](#research-context-wth-raft-and-the-agrotrustchain-framework)
15. [Implementation Status vs. Paper](#implementation-status-vs-paper)
16. [Known Limitations](#known-limitations)
17. [Future Work](#future-work)
18. [Authors](#authors)

---

## Motivation

Modern food supply chains span farmers, agriculture boards, processors, distributors, and
retailers. Each hand-off is an opportunity for contamination, fraud, mislabelling, or simple loss
of provenance information. Traditional traceability systems are centralised, which creates three
problems:

- **Data silos** — each participant keeps their own records, in their own format.
- **Tamper risk** — a single administrator can rewrite history with no trace.
- **Opacity** — consumers and regulators have no independent way to verify a claim.

A distributed ledger removes the single point of trust. Once a transaction is committed, it is
immutable, independently verifiable, and auditable end-to-end — "farm to fork".

## What the System Does

- **Registers supply-chain participants**: agriculture boards, farmers, buyers.
- **Maintains a product catalogue** with package size and price.
- **Records transactions** linking a board, a farmer, a buyer, a product, quantity, price, GST
  number, and effective date.
- **Anchors each transaction on-chain** by invoking a Solidity contract on a private Ethereum
  network through Web3.py at the moment the transaction is created.
- **Generates a hash chain** over pending transactions, computing a SHA-256 digest per record and
  linking it to the previous record's hash.
- **Produces an audit report** showing each transaction with its hash and previous hash, so any
  break in the chain is immediately visible.
- **Enforces role-based access** so each module (boards, buyers, farmers, products, roles,
  transactions, users) is gated by per-role permission flags.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                            │
│   Jinja2 templates + Bootstrap 5 (sidebar shell defined in Home.html) │
│   Login → Dashboard → module listing/operation pages → audit report   │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTP (forms, GET/POST)
┌───────────────────────────────▼──────────────────────────────────────┐
│                        Application Layer                             │
│   Flask — AgricultureFoodSupplyChainV1Server.py                      │
│   • Session/role state  • RBAC gate (process_role)                   │
│   • CRUD orchestration  • Hash-chain generation & reporting          │
└──────────────┬───────────────────────────────┬───────────────────────┘
               │                               │
     ┌─────────▼─────────┐          ┌──────────▼──────────────┐
     │   Model Layer     │          │   Blockchain Middleware │
     │  *Model.py (DAO)  │          │        Web3.py          │
     │  pyodbc / T-SQL   │          │  HTTPProvider :7545     │
     └─────────┬─────────┘          └──────────┬──────────────┘
               │                               │
     ┌─────────▼─────────┐          ┌──────────▼──────────────┐
     │  MS SQL Server    │          │  Ganache private chain  │
     │  AgricultureFood  │          │  network id 5777        │
     │  SupplyChainV1    │          │  Solidity 0.8.10 (Truffle)│
     └───────────────────┘          └─────────────────────────┘
```

**Two ledgers, one truth.** SQL Server holds the queryable operational state (fast listings,
joins, reports). Ethereum holds the immutable attestation. The SHA-256 `hash`/`prevHash` columns
give a third, self-contained integrity check that works even when the chain is offline.

## Repository Layout

```
MAJOR PROJECT/
├── AgricultureFoodSupplyChain/                    # Flask application
│   ├── AgricultureFoodSupplyChainV1DB.bak         # SQL Server database backup (restore this)
│   └── AgricultureFoodSupplyChain/
│       └── src/
│           ├── AgricultureFoodSupplyChainV1Server.py  # Flask app — all routes (~900 lines)
│           ├── Constants.py                       # DB connection string + contract address
│           ├── AgricultureBoardModel.py           # DAO: AgricultureBoard table
│           ├── BuyerModel.py                      # DAO: Buyer table
│           ├── FarmerModel.py                     # DAO: Farmer table
│           ├── ProductModel.py                    # DAO: Product table
│           ├── RoleModel.py                       # DAO: Role table (permission flags)
│           ├── UsersModel.py                      # DAO: Users table
│           ├── TransactionDetailsModel.py         # DAO + Web3 on-chain write
│           ├── templates/                         # 22 Jinja2 templates
│           │   ├── Home.html                      # Base layout (sidebar + topbar)
│           │   ├── Login.html, Dashboard.html, Information.html
│           │   ├── ChangePassword.html
│           │   ├── <Entity>Listing.html           # Table view per entity
│           │   ├── <Entity>Operation.html         # Create / Edit / Delete form per entity
│           │   ├── BlockChainGeneration.html      # Pending vs. generated block counts
│           │   ├── BlockchainGenerationResult.html
│           │   └── BlockChainReport.html          # Hash / prevHash audit trail
│           └── static/                            # Bootstrap, jQuery, custom CSS, assets
│               ├── agri-modern.css                # Project theme
│               ├── charts/, UPLOADED_FILES/       # Output/upload directories
│               └── bootstrap.*, jquery.min.js, metisMenu, simplebar, waves
│
├── AgricultureFoodSupplyChain-Truffle/            # Ethereum / Truffle project
│   ├── contracts/
│   │   ├── AgricultureBoardContract.sol           # Per-entity transaction recorders
│   │   ├── BuyerContract.sol
│   │   ├── FarmerContract.sol
│   │   ├── ProductContract.sol
│   │   ├── RoleContract.sol
│   │   ├── TransactionDetailsContract.sol         # ← the one the Flask app calls
│   │   ├── UsersContract.sol
│   │   ├── AgroCoin.sol                           # ERC20-style token (AGC, supply 1,000,000)
│   │   ├── TrustCoin.sol                          # ERC20-style token (TRC, supply 500,000)
│   │   └── Migrations.sol
│   ├── migrations/                                # Truffle deployment scripts (1–8)
│   ├── build/contracts/*.json                     # Compiled ABIs + deployed addresses
│   └── truffle-config.js                          # solc 0.8.10, dev network 127.0.0.1:7545
│
├── Major Research Paper.md                        # The research paper
├── requirements.txt                               # Python dependencies
├── .gitignore
└── README.md                                      # This file
```

## Technology Stack

| Layer | Technology |
| --- | --- |
| Language (backend) | Python 3.10 |
| Web framework | Flask |
| Templating | Jinja2 |
| Frontend | Bootstrap 5, jQuery, custom CSS (`agri-modern.css`) |
| Database | Microsoft SQL Server (SQL Server Express), accessed via `pyodbc` |
| Blockchain | Ethereum (private) via Ganache, network id `5777`, RPC `127.0.0.1:7545` |
| Smart contracts | Solidity `0.8.10` (compiled with optimizer, `evmVersion: byzantium`) |
| Contract tooling | Truffle |
| Blockchain middleware | Web3.py (`HTTPProvider`) |
| Hashing | `hashlib` SHA-256 over `json.dumps(..., sort_keys=True)` |
| IDE project files | JetBrains PyCharm (`.idea/`) |

## Data Model

Seven tables in the `AgricultureFoodSupplyChainV1` database. Primary keys on the entity tables are
UUID strings generated in Python (`uuid.uuid4()`).

**`AgricultureBoard`** — regulatory/governance body
`agricultureBoardID` (PK), `agricultureBoardName`, `contactNbr`, `emailID`, `address`, `city`,
`county`, `postcode`, `country`

**`Farmer`** — producer
`farmerID` (PK), `farmerName`, `contactNbr`, `emailID`, `address`, `city`, `county`, `postcode`,
`country`, `adharNumber`

**`Buyer`** — purchaser/distributor
`buyerID` (PK), `buyerName`, `contactNbr`, `emailID`, `address`, `city`, `county`, `postcode`,
`country`, `inbusiness`, `adharNumber`

**`Product`** — catalogue item
`productID` (PK), `productName`, `packageSize`, `price`

**`Role`** — permission profile (one boolean per module)
`roleID` (PK), `roleName`, `canRole`, `canUsers`, `canAgricultureBoard`, `canBuyer`, `canFarmer`,
`canProduct`, `canTransactionDetails`

**`Users`** — application login
`userID` (PK), `userName`, `emailid`, `password`, `contactNo`, `isActive`, `roleID` (FK → Role)

**`TransactionDetails`** — the traceability record and the unit of blockchain anchoring
`orderID` (PK), `agricultureBoardID` (FK), `gstNbr`, `buyerID` (FK), `farmerID` (FK), `effDate`,
`productID` (FK), `price`, `qty`, `isBlockChainGenerated`, `hash`, `prevHash`, `sequenceNumber`

`sequenceNumber` establishes the ordering of the hash chain. `isBlockChainGenerated` marks whether
a record has already been sealed into the chain.

## Smart Contracts

All seven entity contracts share the same interface — a lightweight on-chain recorder that stores
the last transaction written for that entity:

```solidity
contract TransactionDetailsContract {
    string public agricultureBoardID;
    string public buyerID;
    string public farmerID;
    string public productID;
    int public price;
    int public qty;

    function perform_transactions(
        string memory _agricultureBoardID,
        string memory _buyerID,
        string memory _farmerID,
        string memory _productID,
        int _price,
        int _qty
    ) public { /* assigns each field */ }
}
```

`TransactionDetailsModel.insert()` is the live integration point. After the row is committed to SQL
Server it connects to Ganache, loads the ABI from
`AgricultureFoodSupplyChain-Truffle/build/contracts/TransactionDetailsContract.json`, sends
`perform_transactions(...)` from `accounts[0]`, and waits for the receipt:

```python
w3 = Web3(HTTPProvider('http://localhost:7545'))
contract = w3.eth.contract(address=contract_address, abi=contract_abi)
tx_hash = contract.functions.perform_transactions(
    str(obj.agricultureBoardID), str(obj.buyerID), str(obj.farmerID),
    str(obj.productID), int(obj.price), int(obj.qty)
).transact({'from': w3.eth.accounts[0]})
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
```

**Token contracts.** `AgroCoin` (AGC, 1,000,000 supply) and `TrustCoin` (TRC, 500,000 supply) are
minimal balance/transfer contracts deployed alongside the entity contracts. They are the on-chain
substrate for the incentive and reputation economy described in the paper (rewarding honest
reporting, staking against quality claims). They compile and deploy via migration `3_deploy_tokens.js`
but are **not yet called from the Flask application**.

### Deployed addresses (Ganache network 5777, from the checked-in build artifacts)

| Contract | Address |
| --- | --- |
| Migrations | `0x56253399286a84B78aB1981EaC626A10B19C2d29` |
| AgricultureBoardContract | `0xe7D2d3c13f821bF30b888DE27F5c3215716489C5` |
| BuyerContract | `0x5566ECfC86003c9E34D0A826f1DA15310814bf7c` |
| FarmerContract | `0x65E7B300126C62a35af1e282a1Be2268E5cB9e98` |
| ProductContract | `0xF01D28806b1633b0003518d97574ee0FB44917C9` |
| RoleContract | `0x1A5e4CeDeF3b5eC15516A65B63E32d9C0B0B38De` |
| TransactionDetailsContract | `0x8Ca603d35d7a384b52887dd05BEAbb906d5331D5` |
| UsersContract | `0xaF29C54F86d2046892488ac81e2aC33FeA68161E` |
| AgroCoin | `0x5778b973EB121F02E035415d4e0b58a232c2E59A` |
| TrustCoin | `0x92F40dFF7c6693DC47391Cd23EF914912601E732` |

> These addresses are specific to one Ganache workspace. **Every fresh `truffle migrate` produces
> new addresses** — see the setup notes below.

## The Hash Chain (Block Generation)

Independent of the Ethereum layer, the app maintains its own append-only hash chain over
`TransactionDetails`. This is the "blockchain report" the auditor reads.

**`/BlockChainGeneration`** counts how many transactions are already sealed
(`isBlockChainGenerated = 1`) and how many are pending.

**`/ProcessBlockchainGeneration`** seals the pending ones:

1. Find the hash of the last already-sealed record (by `sequenceNumber`) — this becomes the
   starting `prevHash`.
2. For each pending record in `sequenceNumber` order:
   - Concatenate `agricultureBoardID + gstNbr + buyerID + farmerID` into the block payload.
   - Serialise deterministically: `json.dumps(payload, sort_keys=True).encode('utf-8')`.
   - `block_hash = hashlib.sha256(serialized).hexdigest()`.
   - Write `hash = block_hash`, `prevHash = <previous>`, `isBlockChainGenerated = 1`.
   - Carry `block_hash` forward as the next record's `prevHash`.

**`/BlockChainReport`** renders the full chain newest-first, so an auditor can walk backwards and
verify that each record's `prevHash` matches its predecessor's `hash`. Any edit to a sealed
transaction breaks the link and is visible immediately.

## Role-Based Access Control

Every protected route calls `process_role(option_id)` before doing any work. The mapping is:

| `option_id` | Module | Role flag |
| --- | --- | --- |
| 0 | Agriculture Board | `canAgricultureBoard` |
| 1 | Buyer | `canBuyer` |
| 2 | Farmer | `canFarmer` |
| 3 | Product | `canProduct` |
| 4 | Role | `canRole` |
| 5 | Transaction Details | `canTransactionDetails` |
| 6 | Users | `canUsers` |

On login the user's `Role` row is loaded into a `RoleModel` and held in application state. If the
flag is false, the request is redirected to `/Information` with an explanatory message. If no role
is loaded at all (e.g. direct URL access without logging in), the user is told to log out and
retry.

## Application Routes

| Route | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Login page |
| `/processLogin` | POST | Authenticate, load role, show dashboard |
| `/Dashboard` | GET | Landing workspace with stats and module cards |
| `/Information` | GET | Message/error page (permission denials, etc.) |
| `/ChangePassword`, `/ProcessChangePassword` | GET, POST | Password change |
| `/AgricultureBoardListing` / `Operation` / `ProcessOperation` | GET, GET, POST | Board CRUD |
| `/BuyerListing` / `Operation` / `ProcessOperation` | GET, GET, POST | Buyer CRUD |
| `/FarmerListing` / `Operation` / `ProcessOperation` | GET, GET, POST | Farmer CRUD |
| `/ProductListing` / `Operation` / `ProcessOperation` | GET, GET, POST | Product CRUD |
| `/RoleListing` / `Operation` / `ProcessOperation` | GET, GET, POST | Role CRUD |
| `/TransactionDetailsListing` / `Operation` / `ProcessOperation` | GET, GET, POST | Transaction CRUD + on-chain write |
| `/UsersListing` / `Operation` / `ProcessOperation` | GET, GET, POST | User CRUD |
| `/BlockChainGeneration` | GET | Pending vs. sealed block counts |
| `/ProcessBlockchainGeneration` | POST | Seal pending transactions into the hash chain |
| `/BlockChainReport` | GET | Full hash-chain audit trail |

Each `*Operation` route is driven by an `operation` query parameter of `Create`, `Edit`, or
`Delete`, and each `Process*Operation` route dispatches on the same value posted from the form.

## Setup and Installation

### Prerequisites

- **Windows** with **Microsoft SQL Server** (Express edition is fine) — the app uses the
  `{SQL Server}` ODBC driver with Integrated Security. The connection string in `Constants.py` is
  Windows-specific.
- **Python 3.10**
- **Node.js** and **Truffle** (`npm install -g truffle`)
- **Ganache** (GUI or CLI), configured to serve on port **7545** with network id **5777**

### 1. Restore the database

Restore `AgricultureFoodSupplyChain/AgricultureFoodSupplyChainV1DB.bak` in SQL Server Management
Studio as a database named **`AgricultureFoodSupplyChainV1`**. This brings the schema and any seed
data (including the initial user and role rows needed to log in).

### 2. Configure the connection

Edit `AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/src/Constants.py` and set `serverName`
to your SQL Server instance:

```python
serverName = "YOURPC\\SQLEXPRESS"     # currently: MADHAVNAIRPC\SQLEXPRESS
databaseName = "AgricultureFoodSupplyChainV1"
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

The project depends on exactly three third-party packages — `Flask`, `pyodbc`, and `web3` —
everything else it imports (`hashlib`, `json`, `uuid`, `datetime`, `time`, `os`, `pprint`) is in
the standard library.

Two notes on `requirements.txt`:

- **`pyodbc` needs a system ODBC driver**, which pip does not install. On Windows the `{SQL Server}`
  driver ships with SQL Server itself. On Linux/macOS you would install `msodbcsql18` and update
  the connection string in `Constants.py`.
- **`web3` is capped below v7.** The code uses the v5/v6 API (`from web3 import Web3, HTTPProvider`
  and `w3.eth.wait_for_transaction_receipt(...)`); v7 reorganised parts of that surface. If you
  upgrade past v6, re-test `TransactionDetailsModel.insert()`.

### 4. Start Ganache and deploy the contracts

Launch Ganache on `127.0.0.1:7545`, then:

```bash
cd AgricultureFoodSupplyChain-Truffle
truffle compile
truffle migrate --reset
```

### 5. Update the contract address ⚠️

`truffle migrate` assigns **new addresses on every run**. Copy the freshly deployed
`TransactionDetailsContract` address from the migration output and set it in `Constants.py`:

```python
contract_address = "0x...."   # must match the deployed TransactionDetailsContract
```

If this is stale, creating a transaction will fail or silently write to the wrong contract. (The
value currently committed in `Constants.py` does not match the address in the checked-in build
artifacts, so expect to set this on first run.)

## Running the Project

Run the Flask app **from the `src` directory** — `TransactionDetailsModel.py` loads the contract
ABI via the relative path `../../../AgricultureFoodSupplyChain-Truffle/build/contracts/...`, which
only resolves correctly from there:

```bash
cd "AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/src"
python AgricultureFoodSupplyChainV1Server.py
```

The app starts on Flask's default `http://127.0.0.1:5000/`. Open it and log in with a user from the
restored `Users` table (the account must have `isActive = 1`).

## Typical Workflow

1. **Log in** — credentials are validated against `Users`, and the associated `Role` determines
   which sidebar modules are usable.
2. **Register master data** — add Agriculture Boards, Farmers, Buyers, and Products.
3. **Record a transaction** — from *Transactions → Create*, select board, farmer, buyer, and
   product; enter GST number, effective date, price, and quantity. On save the row is inserted into
   SQL Server **and** `perform_transactions(...)` is executed on the Ethereum contract; the block
   receipt is awaited before the request returns.
4. **Generate blocks** — visit *Generate Blocks* to see how many transactions are unsealed, then
   submit to compute SHA-256 hashes and link each record to its predecessor.
5. **Audit** — open *Blockchain Report* to inspect the chain: each row shows its own hash and the
   hash of the record before it. A mismatch anywhere proves tampering.

## Research Context: WTH-Raft and the AgroTrustChain Framework

The accompanying paper (`Major Research Paper.md`) situates this implementation against the
**Weighted Two-Hop Raft (WTH-Raft)** consensus mechanism and proposes AgroTrustChain as a
smart-contract-driven successor.

### The problem with existing approaches

- **Proof of Work** — secure but computationally expensive and low-throughput; unusable for the
  high-frequency sensor and logistics data that agriculture generates.
- **Standard Raft** — simple and strongly consistent, but the leader node becomes a bottleneck as
  the network grows, and Raft assumes a trusted environment with no defence against Byzantine
  (malicious) participants such as a supplier falsifying quality data.
- **WTH-Raft** — improves on Raft with two ideas:
  1. **Hierarchical two-hop structure** — nodes are stratified into a primary tier (group leaders)
     and secondary clusters. The leader broadcasts only to primary nodes, which forward in
     parallel to their clusters, sharding the communication load.
  2. **Weighted voting** — each node carries a **Q-Score** (verified product quality) and an
     **R-Score** (historical honesty and uptime); consensus weight is derived dynamically from
     both, so misbehaving nodes lose influence.

  Reported gains: roughly **25–30% lower consensus latency** than flat architectures, stable
  throughput past 50 nodes where PBFT and standard Raft degrade sharply, and consensus success
  above **94% even with 20% malicious nodes**.

### The remaining gaps WTH-Raft does not close

WTH-Raft still runs in a **permissioned** environment with a predetermined node set, retains
**leader-based coordination** (partial centralisation and a throughput bottleneck), depends on an
**external scoring system** for weights (added complexity and bias risk), has **no programmable
automation** for compliance policies (certificate validation, expiry tracking, penalties), and
offers **limited interoperability** with public Ethereum ecosystems — so consumers cannot verify
provenance independently of the supply-chain participants.

### The AgroTrustChain proposal

AgroTrustChain replaces leader-dependent voting with Ethereum's decentralised validation model plus
a **hybrid reputation-quality** scheme:

- **On-chain reputation indexing** — R-Scores maintained in contract storage rather than by an
  external authority.
- **Off-chain quality validation** — Q-Scores sourced from inspection and, in future work, from IoT
  sensors and computer-vision models (the paper cites ResNet-34 / YOLOv4-tiny with CBAM attention
  achieving >99% accuracy on agricultural quality tasks).
- **Automated smart-contract penalties** — a supplier submitting inconsistent quality data has
  reputation deducted automatically by the contract, neutralising Byzantine behaviour without
  human intervention.
- **Programmable compliance** — certificate hashes, expiry dates, and quality thresholds verified
  by contract logic *before* a transaction is admitted.

The result is a self-regulating ecosystem: honest reporting raises your weight, dishonest reporting
costs you standing, and the enforcement is automatic and publicly verifiable.

## Implementation Status vs. Paper

To be precise about what the code in this repository does today versus what the paper proposes:

| Component | Status |
| --- | --- |
| Flask stakeholder interface | ✅ Implemented — 22 templates, 7 CRUD modules |
| SQL Server persistence layer | ✅ Implemented — DAO per entity |
| Role-based access control | ✅ Implemented — per-module permission flags |
| Private Ethereum network (Ganache) | ✅ Implemented — network 5777, port 7545 |
| Solidity contracts + Truffle migrations | ✅ Implemented — 10 contracts deployed |
| Web3.py middleware | ✅ Implemented — on-chain write on transaction insert |
| SHA-256 hash chain + audit report | ✅ Implemented — generation and reporting routes |
| AgroCoin / TrustCoin token contracts | ⚠️ Deployed but not yet wired into the application |
| Q-Score / R-Score on-chain scoring | 🔬 Described in the paper; not yet in the contracts |
| Automated penalty mechanism | 🔬 Described in the paper; not yet in the contracts |
| WTH-Raft two-hop consensus simulation | 🔬 Evaluated in the paper; not part of this codebase |
| IoT sensor / computer-vision quality feed | 🔬 Future work |

The contracts in `contracts/` are deliberately simple recorders — they establish the on-chain
anchoring path end-to-end. Extending `TransactionDetailsContract` with reputation state, quality
thresholds, and penalty logic is the natural next step and is where the paper's contribution
becomes executable.

## Known Limitations

This is an academic project, and the code has rough edges worth naming before anyone deploys it:

- **SQL injection** — the login, password-change, and block-generation paths build SQL by string
  concatenation (`"... WHERE emailid = '" + emailid + "'"`). The entity DAOs correctly use
  parameterised queries; these routes should be brought in line.
- **Plaintext passwords** — credentials are stored and compared in clear text. They should be
  salted and hashed (bcrypt/Argon2).
- **Module-level session state** — `user_id`, `emailid`, and `role_object` are Python globals, not
  Flask sessions. The application is effectively single-user and not safe for concurrent access.
- **Windows/SQL Server coupling** — the `{SQL Server}` ODBC driver and Integrated Security make the
  data layer Windows-only.
- **Hardcoded contract address** — `contract_address` in `Constants.py` must be updated manually
  after each migration.
- **Partial hash payload** — the block hash covers only four columns (`agricultureBoardID`,
  `gstNbr`, `buyerID`, `farmerID`). Product, price, quantity, and date are not hashed, so changes
  to those fields would not break the chain.
- **Relative ABI path** — the app must be launched from the `src` directory.
- **Contract duplication** — the seven entity contracts are byte-for-byte identical apart from
  their names; a single parameterised contract would serve.
- **No tests** — `AgricultureFoodSupplyChain-Truffle/test/` is empty.

## Future Work

- Implement Q-Score and R-Score as on-chain state with the weighted-scoring formula from the paper.
- Add the automated penalty mechanism and certificate/expiry validation to the transaction contract.
- Wire AgroCoin and TrustCoin into an incentive loop that rewards honest reporting.
- Ingest real-time IoT sensor data (temperature, humidity, storage conditions) into the quality score.
- Integrate computer-vision quality assessment to remove human error from the reputation engine.
- Move bulk data (images, environmental logs) to IPFS and store only content hashes on-chain,
  avoiding the "storage explosion" problem.
- Harden authentication: hashed passwords, Flask sessions, CSRF protection, parameterised queries
  everywhere.
- Deploy to a public or consortium testnet so consumers can verify provenance independently.
- Add a consumer-facing traceability lookup (scan a code, see the full farm-to-fork history).

## Authors

This project was designed and built by:

- **Madhav Nair**
- **Ishaan Chaturvedi**
- **Kunal Saha**

Research paper: *Enhancing and Securing Agricultural Products Traceability Using Ethereum Based
AgroTrustChain Framework* — included in this repository as `Research Paper.pdf`.

**Keywords:** Raft consensus, agri-food supply chain, blockchain, weight allocation, Ethereum,
smart contracts, traceability.
