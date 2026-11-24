# AgroTrustChain — Blockchain-Based Agricultural Food Supply Chain Traceability

A blockchain-enabled traceability system for the agri-food supply chain, built as a Flask web
application backed by SQL Server for operational records and a private Ethereum network (Ganache
+ Truffle + Solidity) for tamper-evident transaction anchoring.

Every purchase transaction between a farmer, a buyer, and an agriculture board is written to a
relational database, mirrored onto an Ethereum smart contract through Web3.py, and chained into a
SHA-256 hash ledger (`hash` / `prevHash`) that a web report re-verifies on every view.

**Quick start:** with Docker installed, run `docker compose up --build`, open
<http://localhost:5000> and log in as `1@1.com` / `1`. See [Setup with Docker](#setup-with-docker), or
[CONTRIBUTING.md](CONTRIBUTING.md) to run it without Docker.

Created by **Madhav Nair**, **Ishaan Chaturvedi**, and **Kunal Saha**.

This repository is the implementation companion to the research paper *"Enhancing and Securing
Agricultural Products Traceability Using Ethereum Based AgroTrustChain Framework"*.

---

## Table of Contents

1. [Motivation](#motivation)
2. [What the System Does](#what-the-system-does)
3. [Architecture](#architecture)
4. [Technology Stack](#technology-stack)
5. [Data Model](#data-model)
6. [Smart Contracts](#smart-contracts)
7. [The Hash Chain (Block Generation)](#the-hash-chain-block-generation)
8. [Role-Based Access Control](#role-based-access-control)
9. [Application Routes](#application-routes)
10. [Setup with Docker](#setup-with-docker)
11. [Typical Workflow](#typical-workflow)
12. [Research Context: WTH-Raft and the AgroTrustChain Framework](#research-context-wth-raft-and-the-agrotrustchain-framework)
13. [Implementation Status vs. Paper](#implementation-status-vs-paper)
14. [Known Limitations](#known-limitations)
15. [Future Work](#future-work)
16. [Authors](#authors)

Also in this repository: [CONTRIBUTING.md](CONTRIBUTING.md) (development setup, repository layout, conventions) and [SECURITY.md](SECURITY.md) (security status and known limitations).

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
- **Generates a hash chain** over pending transactions, computing a SHA-256 digest of each
  record's full contents together with the previous record's hash.
- **Produces an audit report** that recomputes every hash and checks every link, flagging any
  sealed transaction that was edited, deleted or re-ordered.
- **Enforces role-based access** so each module (boards, buyers, farmers, products, roles,
  transactions, users) is gated by per-role permission flags, with a separate login per browser.

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

Under Docker each box above is a container: `db` (SQL Server 2022), `ganache`, a one-shot
`contracts` container that runs `truffle migrate`, and `app` (Flask under gunicorn).

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
| Containers | Docker Compose: SQL Server 2022, Ganache v7, Node 18 + Truffle 5.11, Python 3.11 + gunicorn |
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

`sequenceNumber` establishes the ordering of the hash chain. New transactions take the next free
number, and `migrate.sql` adds a unique index on it. `isBlockChainGenerated` marks whether a record
has already been sealed into the chain.

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
Server it connects to Ganache, loads `TransactionDetailsContract.json` from Truffle's build folder,
looks up the contract address for the network Ganache reports, sends `perform_transactions(...)`
from `accounts[0]`, and waits for the receipt:

```python
w3 = Web3(HTTPProvider(Constants.eth_rpc_url))
contract = _load_transaction_contract(w3)   # ABI + address from the Truffle artifact
tx_hash = contract.functions.perform_transactions(
    str(obj.agricultureBoardID), str(obj.buyerID), str(obj.farmerID),
    str(obj.productID), int(float(obj.price)), int(float(obj.qty))
).transact({'from': w3.eth.accounts[0]})
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
```

Because the address comes from the artifact that `truffle migrate` writes, it no longer has to be
copied into `Constants.py` after each deployment. Setting the `CONTRACT_ADDRESS` environment
variable still overrides it.

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
> new addresses**, which the app picks up from the artifacts automatically. The Docker stack
> deploys its own copies and keeps their artifacts in a Docker volume, so these files are not
> modified.

## The Hash Chain (Block Generation)

Independent of the Ethereum layer, the app maintains its own append-only hash chain over
`TransactionDetails` ([HashChain.py](AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/src/HashChain.py)).
This is the "blockchain report" the auditor reads.

**`/BlockChainGeneration`** counts how many transactions are already sealed
(`isBlockChainGenerated = 1`) and how many are pending.

**`/ProcessBlockchainGeneration`** appends the pending ones, in one database transaction:

1. The tip of the chain is the sealed record with the highest `sequenceNumber`; its `hash` becomes
   the starting `prevHash` (empty for the first block).
2. For each pending record in `sequenceNumber` order:
   - Build the block payload from **every** business field (`orderID`, `agricultureBoardID`,
     `gstNbr`, `buyerID`, `farmerID`, `effDate`, `productID`, `price`, `qty`), plus
     `sequenceNumber` and `prevHash`.
   - Serialise deterministically: `json.dumps(payload, sort_keys=True, separators=(",", ":"))`.
   - `hash = sha256(serialized)`; store `hash`, `prevHash`, `isBlockChainGenerated = 1`.
   - Carry `hash` forward as the next record's `prevHash`.

**`/BlockChainReport`** walks the chain from the first block, recomputes each hash and checks each
link, and marks every block *Verified*, *Tampered* or *Pending*:

| What happened to a sealed record | How the report shows it |
| --- | --- |
| Any field edited (in the app or directly in SQL) | That block: "Data was changed after this block was sealed" |
| Record deleted | The next block: "Link broken" |
| Record re-sealed with a fresh hash | The next block: "Link broken" |

Editing a sealed transaction in the app is allowed, but the form warns that the edit will show as
tampering.

**What it cannot catch:** someone with write access to the database who changes a record *and
recomputes every later hash* produces a chain that verifies. Catching that needs the latest hash
anchored somewhere they cannot write, such as the Ethereum contract (see Future Work).

### Re-sealing an old chain

Records sealed by versions of the app before this hash format will show as *Tampered*. If you trust
the current data, unseal everything and generate blocks again:

```sql
UPDATE TransactionDetails SET isBlockChainGenerated = 0, hash = '', prevHash = '';
```

Then run `migrate.sql` again (it renumbers duplicate `sequenceNumber`s and adds the unique index)
and use *Generate Blocks*. The database shipped in this repository has no sealed records, so a
fresh setup does not need this.

## Role-Based Access Control

Logging in stores the user's ID in Flask's signed session cookie, so each browser has its own
login. On every request the app reloads the user and their `Role` row from the database. Editing a
role or deactivating a user (`isActive = 0`) therefore takes effect on the user's next click.
*Logout* (`/Logout`) clears the session.

Each protected route is decorated with `@login_required("<flag>", "<module>")`:

| Module | Role flag |
| --- | --- |
| Agriculture Board | `canAgricultureBoard` |
| Buyer | `canBuyer` |
| Farmer | `canFarmer` |
| Product | `canProduct` |
| Role | `canRole` |
| Transaction Details, and the three blockchain pages | `canTransactionDetails` |
| Users | `canUsers` |

Visitors who are not logged in are sent to the login page. Users whose role lacks the flag are
sent to `/Information` with an explanatory message. The dashboard and *Change Password* need a
login but no flag.

## Application Routes

| Route | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Login page |
| `/processLogin` | POST | Authenticate, start the session, redirect to the dashboard |
| `/Logout` | GET | End the session |
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
| `/BlockChainReport` | GET | Re-verify the full hash chain and show the audit trail |

Each `*Operation` route is driven by an `operation` query parameter of `Create`, `Edit`, or
`Delete`, and each `Process*Operation` route dispatches on the same value posted from the form.

## Setup with Docker

Works the same on Linux, macOS and Windows. The only requirement is
[Docker](https://docs.docker.com/get-docker/) with Compose v2. Give Docker at least 4 GB of
memory, since SQL Server alone needs 2 GB.

```bash
git clone https://github.com/MadhavVN011/AgroTrustChain.git
cd AgroTrustChain
docker compose up --build
```

The first run takes a few minutes to download images and build. When the `app` container logs
`Listening at: http://0.0.0.0:5000`, open <http://localhost:5000> and log in with the seeded
account **`1@1.com` / `1`**. Its role has every permission.

What happens on start:

1. `db` starts SQL Server 2022.
2. `db-init` restores `AgricultureFoodSupplyChainV1DB.bak` the first time only, then runs
   `migrate.sql`.
3. `ganache` starts a private chain (network id 5777, chain id 1337, deterministic accounts).
4. `contracts` runs `truffle migrate`, writing the ABIs and addresses to a shared volume.
5. `app` starts once both one-shot jobs have succeeded.

Everyday commands:

| Command | Effect |
| --- | --- |
| `docker compose up -d` | Start in the background |
| `docker compose logs -f app` | Follow the web app's log |
| `docker compose down` | Stop. Database and chain are kept in Docker volumes |
| `docker compose down -v` | Stop and **delete** the database and chain, to start over from the `.bak` |
| `docker compose up --build app` | Rebuild after changing Python code or templates |

**Configuration.** Defaults work without any setup. To change them, copy `.env.example` to `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MSSQL_SA_PASSWORD` | `AgroTrust_Dev_2026!` | SQL Server `sa` password. Set it before the first start: it is stored in the database volume |
| `FLASK_SECRET_KEY` | random per start | Signs login cookies. Set it to stay logged in across restarts |
| `APP_PORT`, `DB_PORT`, `GANACHE_PORT` | 5000, 1433, 7545 | Host ports. Change them if another program, such as Ganache GUI, already uses one |

All ports are bound to `127.0.0.1` only. To browse the database from SSMS or Azure Data Studio,
connect to `localhost,1433` as `sa`. To connect MetaMask or `truffle console`, use
`http://localhost:7545`.

> **Apple Silicon:** Microsoft publishes SQL Server images for x86-64 only. Docker Desktop runs
> them under emulation (enable *Use Rosetta* in its settings).

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
5. **Audit** — open *Blockchain Report*. It recomputes every hash and checks every link, and flags
   each sealed transaction that was changed, deleted or re-ordered.

## Research Context: WTH-Raft and the AgroTrustChain Framework

The accompanying paper ([`Research Paper.pdf`](Research%20Paper.pdf)) situates this implementation against the
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
| SHA-256 hash chain + audit report | ✅ Implemented — full-record hashes, verified on every report view |
| Docker setup | ✅ Implemented — one command brings up the whole stack |
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

This is an academic prototype and is not hardened for production. Security limitations are
listed in [SECURITY.md](SECURITY.md) and other known gaps in
[CONTRIBUTING.md](CONTRIBUTING.md#known-gaps).

## Future Work

- Implement Q-Score and R-Score as on-chain state with the weighted-scoring formula from the paper.
- Add the automated penalty mechanism and certificate/expiry validation to the transaction contract.
- Wire AgroCoin and TrustCoin into an incentive loop that rewards honest reporting.
- Ingest real-time IoT sensor data (temperature, humidity, storage conditions) into the quality score.
- Integrate computer-vision quality assessment to remove human error from the reputation engine.
- Move bulk data (images, environmental logs) to IPFS and store only content hashes on-chain,
  avoiding the "storage explosion" problem.
- Anchor the latest chain hash in the Ethereum contract on every *Generate Blocks*, so even a full
  rewrite of the database chain is detectable.
- Harden authentication: hashed passwords and CSRF tokens (see [SECURITY.md](SECURITY.md)).
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
