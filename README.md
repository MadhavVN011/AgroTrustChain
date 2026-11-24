# AgroTrustChain — Blockchain-Based Agricultural Food Supply Chain Traceability

[![CI/CD](https://github.com/MadhavVN011/AgroTrustChain/actions/workflows/ci.yml/badge.svg)](https://github.com/MadhavVN011/AgroTrustChain/actions/workflows/ci.yml)

A blockchain-enabled traceability system for the agri-food supply chain, built as a Flask web
application backed by SQL Server for operational records and a private Ethereum network (Ganache
+ Truffle + Solidity) for tamper-evident transaction anchoring.

Every purchase transaction between a farmer, a buyer, and an agriculture board is written to a
relational database, mirrored onto an Ethereum smart contract through Web3.py, and chained into a
SHA-256 hash ledger (`hash` / `prevHash`) that a web report re-verifies on every view.

**Quick start:** with Docker installed, run `docker compose up --build`, open
<http://localhost:5000> and log in as `1@1.com` / `1`. See [Setup with Docker](#setup-with-docker), or
[CONTRIBUTING.md](CONTRIBUTING.md) to run it without Docker.

**Live demo:** <https://agrotrustchain.vercel.app>. This is a read-only version with sample data: the
real templates and the real hash-chain verification, but no database or Ethereum node behind it.
It includes a [tampered example](https://agrotrustchain.vercel.app/BlockChainReportTampered).

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
  network through Web3.py at the moment the transaction is created, and stores the resulting
  Ethereum transaction hash with the record.
- **Generates a hash chain** over pending transactions, computing a SHA-256 digest of each
  record's full contents together with the previous record's hash.
- **Anchors the chain's tip on Ethereum** each time blocks are sealed.
- **Admits product batches only if they comply**: certificate hash not revoked, certificate not
  expired, claimed quality above the minimum, all checked by a smart contract.
- **Scores every farmer on-chain** with a Q-Score (inspected quality) and an R-Score (honest
  reporting), combined into a consensus weight **W = αQ + βR**. An inconsistent quality claim is
  **penalised automatically**, and repeat offenders are suspended from trading.
- **Produces an audit report** that recomputes every hash, checks every link and compares the tip
  with the Ethereum anchor, flagging any sealed transaction that was edited, deleted, re-ordered
  or rewritten.
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
│   • Sessions + CSRF     • RBAC gate (@login_required)                │
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
the last transaction written for that entity. `TransactionDetailsContract` also anchors the hash
chain (see [The Hash Chain](#the-hash-chain-block-generation)):

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

    // TransactionDetailsContract only: tip of the application's hash chain.
    address public owner = msg.sender;
    bytes32 public chainHead;
    uint public chainLength;
    event ChainAnchored(uint chainLength, bytes32 chainHead);

    function anchorChain(bytes32 _chainHead, uint _chainLength) public;  // owner only
}
```

`TransactionDetailsModel.insert()` is the live integration point. All Ethereum calls live in
[Blockchain.py](AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/src/Blockchain.py). It loads
`TransactionDetailsContract.json` from Truffle's build folder, looks up the contract address for
the network Ganache reports, and sends transactions from `accounts[0]`:

```python
# TransactionDetailsModel.insert()
obj.ethTxHash = Blockchain.record_transaction(
    obj.agricultureBoardID, obj.buyerID, obj.farmerID, obj.productID, price, qty)
# ...then INSERT the row, including ethTxHash
```

The chain is written **first**. If Ethereum is unreachable, nothing is stored and the user sees an
error, so every database row has an on-chain record. The row keeps the Ethereum transaction hash
(`ethTxHash`), which the Blockchain Report shows.

Because the address comes from the artifact that `truffle migrate` writes, it no longer has to be
copied into `Constants.py` after each deployment. Setting the `CONTRACT_ADDRESS` environment
variable still overrides it.

**Token contracts.** `AgroCoin` (AGC, 1,000,000 supply) and `TrustCoin` (TRC, 500,000 supply) are
minimal balance/transfer contracts deployed alongside the entity contracts. They are the on-chain
substrate for the incentive and reputation economy described in the paper (rewarding honest
reporting, staking against quality claims). They compile and deploy via migration `9_deploy_tokens.js`
but are **not yet called from the Flask application**.

### TraceabilityManagement: compliance, reputation and penalties

[TraceabilityManagement.sol](AgricultureFoodSupplyChain-Truffle/contracts/TraceabilityManagement.sol)
implements the paper's smart-contract layer (Fig. 1). The app uses it from the *Quality &
Reputation* pages:

| Function | What it does |
| --- | --- |
| `registerBatch` | Admits a batch only if the certificate hash is set and not revoked, the certificate has not expired, the claimed quality is at least `minQuality`, and the supplier is not suspended. Otherwise it reverts with the reason, which the app shows. |
| `updateQuality` | Records the off-chain inspection result. Q-Score becomes a moving average of inspected quality. If the claim is within `tolerance` of the inspection, R-Score rises by `honestReward`; otherwise the batch is revoked and R-Score falls by `penalty`. Below `suspendBelow` the supplier is suspended. |
| `revokeCertificate` | Blocks the certificate for new batches and invalidates the batches that used it. |
| `weightOf` | The consensus weight W = (α·Q + β·R) / 100, the paper's "R = αQ + βS". Zero while suspended. |
| `isEligible` | Checked before every new transaction: a suspended farmer cannot trade. |
| `reinstateSupplier`, `setParameters` | Owner-only administration. |

The paper gives no numbers for these rules. The defaults are this implementation's choices:
α = β = 50, reward +2, penalty −20, tolerance 10, minimum quality 40, suspension below R = 20.
Scores and penalties live on-chain. The `Batch` table keeps batch details for listing.

### Deployed addresses (Ganache network 5777, from the checked-in build artifacts)

| Contract | Address |
| --- | --- |
| Migrations | `0x56253399286a84B78aB1981EaC626A10B19C2d29` |
| AgricultureBoardContract | `0xe7D2d3c13f821bF30b888DE27F5c3215716489C5` |
| BuyerContract | `0x5566ECfC86003c9E34D0A826f1DA15310814bf7c` |
| FarmerContract | `0x65E7B300126C62a35af1e282a1Be2268E5cB9e98` |
| ProductContract | `0xF01D28806b1633b0003518d97574ee0FB44917C9` |
| RoleContract | `0x1A5e4CeDeF3b5eC15516A65B63E32d9C0B0B38De` |
| TransactionDetailsContract | none: the contract gained chain anchoring, so redeploy it with `truffle migrate --reset` |
| UsersContract | `0xaF29C54F86d2046892488ac81e2aC33FeA68161E` |
| TraceabilityManagement | none yet: deploy with `truffle migrate` |
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
3. Anchor the new tip on Ethereum: `anchorChain(lastHash, numberOfSealedBlocks)`. If that fails,
   the database transaction is rolled back and nothing is sealed.

Before sealing, the existing chain is compared with the anchor. If they disagree, sealing is
refused: anchoring a new tip on top would hide the evidence.

**`/BlockChainReport`** walks the chain from the first block, recomputes each hash, checks each
link, and compares the tip with the anchor read from Ethereum. It marks every block *Verified*,
*Tampered* or *Pending*:

| What happened to the sealed records | How the report shows it |
| --- | --- |
| A field edited (in the app or directly in SQL) | That block: "Data was changed after this block was sealed" |
| A record deleted, or re-sealed with a fresh hash | The next block: "Link broken" |
| A record changed *and every later hash recomputed* | Banner: the database chain does not match the Ethereum anchor |
| The newest records deleted | Banner: the database chain does not match the Ethereum anchor |
| Ethereum unreachable | Amber banner: hashes and links verified, anchor not confirmed |

Editing a sealed transaction in the app is allowed, but the form warns that the edit will show as
tampering.

**What it still cannot catch:** someone who controls both the database *and* the app's Ethereum
account (the contract owner) can rewrite the chain and re-anchor it. On a public or consortium
network the anchoring history stays visible in the `ChainAnchored` events, but this app does not
audit them.

### Re-sealing an old chain

Records sealed by versions of the app before this hash format will show as *Tampered*. If you trust
the current data, unseal everything and generate blocks again:

```sql
UPDATE TransactionDetails SET isBlockChainGenerated = 0, hash = '', prevHash = '';
```

Then run `migrate.sql` again (it renumbers duplicate `sequenceNumber`s and adds the unique index),
redeploy the contracts so the anchor starts empty (`truffle migrate --reset`; under Docker, delete
the `ganache-data` and `contracts-build` volumes), and use *Generate Blocks*. The database shipped
in this repository has no sealed records, so a fresh setup does not need this.

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
| Farmer, and the Quality & Reputation pages (batches, inspections, reputation) | `canFarmer` |
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
| `/BatchListing`, `/BatchOperation`, `/ProcessBatchOperation` | GET, GET, POST | List and register batches (compliance checked on-chain) |
| `/BatchInspection`, `/ProcessBatchInspection` | GET, POST | Record an inspection; applies the reputation rules and penalties |
| `/ProcessRevokeCertificate` | POST | Revoke a batch's certificate |
| `/Reputation`, `/ProcessReinstateSupplier` | GET, POST | On-chain Q/R scores and weights; lift a suspension |
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
| `docker compose run --rm tests` | Run the Python tests (no database or chain needed) |
| `docker compose run --rm contracts truffle test` | Run the Solidity contract tests against Ganache |

On every start the app also hashes any plain-text passwords left in the database
(`upgrade_passwords.py`), so the seeded password is stored hashed from the first run.

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

1. **Log in** — the password is checked against the salted hash in `Users`, and the associated
   `Role` determines which sidebar modules are usable.
2. **Register master data** — add Agriculture Boards, Farmers, Buyers, and Products.
3. **Register and inspect batches** — under *Batches*, register a farmer's batch with its
   certificate and claimed quality; the contract rejects non-compliant batches. Record the
   inspection result: a consistent claim raises the farmer's R-Score, and an inconsistent one is
   penalised automatically. *Reputation* shows the live scores and weights.
4. **Record a transaction** — from *Transactions → Create*, select board, farmer, buyer, and
   product; enter GST number, effective date, price, and quantity. On save,
   `perform_transactions(...)` is executed on the Ethereum contract and its receipt awaited; only
   then is the row inserted into SQL Server, together with the Ethereum transaction hash. A farmer
   suspended by the reputation engine cannot be part of a new transaction.
5. **Generate blocks** — visit *Generate Blocks* to see how many transactions are unsealed, then
   submit to compute SHA-256 hashes, link each record to its predecessor and anchor the new tip
   on Ethereum.
6. **Audit** — open *Blockchain Report*. It recomputes every hash, checks every link and compares
   the tip with the Ethereum anchor, flagging any sealed transaction that was changed, deleted,
   re-ordered or rewritten.

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
| Hash chain anchored on Ethereum | ✅ Implemented — tip anchored on every seal, compared on every report view |
| Automated tests | ✅ Implemented — Python (pytest) and Solidity (Truffle) suites |
| Docker setup | ✅ Implemented — one command brings up the whole stack |
| AgroCoin / TrustCoin token contracts | ⚠️ Deployed but not yet wired into the application |
| Q-Score / R-Score on-chain scoring | ✅ Implemented — `TraceabilityManagement`, weight W = αQ + βR, shown on *Reputation* |
| Automated penalty mechanism | ✅ Implemented — inconsistent claims revoke the batch, cut R-Score and can suspend the farmer |
| Certificate, expiry and quality compliance | ✅ Implemented — checked on-chain before a batch is admitted; suspended farmers cannot trade |
| WTH-Raft two-hop consensus simulation | ✅ Implemented — [simulation/](simulation/), compared with Raft and PBFT; see [results](simulation/results/RESULTS.md) |
| IoT sensor / computer-vision quality feed | 🔬 Future work |

**What the simulation found.** [simulation/results/RESULTS.md](simulation/results/RESULTS.md)
checks each of the paper's claims against the simulated numbers:

- **Consensus success: confirmed.** With 20% malicious nodes, WTH-Raft decided 99.9% of rounds
  correctly (the paper claims above 94%), against 75% for Raft. It held against "sleeper" attackers
  that build up reputation first.
- **Throughput: partly confirmed.** WTH-Raft is far faster than Raft and PBFT at scale, but its
  TPS still falls as the network grows, rather than staying flat.
- **Latency: partly confirmed.** WTH-Raft is 22–60% faster than Raft from 100 to 200 nodes, but
  slower in small networks, because of the extra hop.

The security result rests on one strong assumption: an off-chain inspection reveals the truth
after every round. The simulation [README](simulation/README.md) states which parameters come from
the paper and which are this implementation's choices.

## Known Limitations

This is an academic prototype and is not hardened for production. Security limitations are
listed in [SECURITY.md](SECURITY.md) and other known gaps in
[CONTRIBUTING.md](CONTRIBUTING.md#known-gaps).

## Future Work

- Wire AgroCoin and TrustCoin into the reputation engine: stake TrustCoin on quality claims and
  slash it alongside the R-Score penalty, and reward honest reporting with AgroCoin.
- Run the simulation with a weaker inspection oracle (delayed, sampled, sometimes wrong), which is
  the main open question in the Byzantine results.
- Ingest real-time IoT sensor data (temperature, humidity, storage conditions) into the quality score.
- Integrate computer-vision quality assessment to remove human error from the reputation engine.
- Move bulk data (images, environmental logs) to IPFS and store only content hashes on-chain,
  avoiding the "storage explosion" problem.
- Audit the full history of `ChainAnchored` events, so a re-anchored chain is also detectable.
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
