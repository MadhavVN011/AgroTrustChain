# Contributing to AgroTrustChain

This guide covers the development setup and the conventions the code relies on. For an overview
of what the system does, see the [README](README.md).

## Contents

1. [Development with Docker](#development-with-docker)
2. [Running Without Docker (Windows)](#running-without-docker-windows)
3. [Repository Layout](#repository-layout)
4. [Conventions](#conventions)
5. [Tests](#tests)
6. [CI/CD and the Vercel Demo](#cicd-and-the-vercel-demo)
7. [Known Gaps](#known-gaps)
8. [Submitting Changes](#submitting-changes)

## Development with Docker

The quickest loop is the Docker stack described in the
[README](README.md#setup-with-docker):

```bash
docker compose up -d --build        # first start, or after changing code
docker compose logs -f app          # watch requests and tracebacks
docker compose up -d --build app    # rebuild just the web app after an edit
docker compose down -v              # throw away the database and chain, back to the .bak
```

- **Python or template changes:** rebuild `app`. The code is copied into the image, not mounted.
- **Solidity or migration changes:** run `docker compose up -d --build contracts`. If you changed
  an existing contract, run `docker compose down -v` first so it is redeployed from scratch.
- **Schema changes:** add them to `AgricultureFoodSupplyChain/migrate.sql` (see
  [Conventions](#conventions)). They run on every start.
- **Querying the database:**
  `docker compose exec db /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -d AgricultureFoodSupplyChainV1`,
  or connect SSMS / Azure Data Studio to `localhost,1433`.

## Running Without Docker (Windows)

The original setup.

### Prerequisites

- **Windows** with **Microsoft SQL Server** (Express edition is fine) — the app uses the
  `{SQL Server}` ODBC driver with Integrated Security by default.
- **Python 3.10+**
- **Node.js** and **Truffle** (`npm install -g truffle`)
- **Ganache** (GUI or CLI), configured to serve on port **7545** with network id **5777**

### 1. Restore the database

Restore `AgricultureFoodSupplyChain/AgricultureFoodSupplyChainV1DB.bak` in SQL Server Management
Studio as a database named **`AgricultureFoodSupplyChainV1`**. This brings the schema and the seed
data, including the `1@1.com` / `1` login.

Then run `AgricultureFoodSupplyChain/migrate.sql` against that database (open it in SSMS and
execute). It gives existing transactions unique sequence numbers and adds a unique index. It is
safe to run more than once.

### 2. Configure the connection

Settings live in `AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/src/Constants.py`, and
each can also be set as an environment variable:

| Environment variable | Default |
| --- | --- |
| `DB_SERVER` | `MADHAVNAIRPC\SQLEXPRESS` (change this to your instance) |
| `DB_NAME` | `AgricultureFoodSupplyChainV1` |
| `DB_DRIVER` | `SQL Server` |
| `DB_USER` / `DB_PASSWORD` | unset, so Windows Integrated Security is used |
| `ETH_RPC_URL` | `http://localhost:7545` |
| `CONTRACT_ADDRESS` | unset, so the address is read from the Truffle artifact |
| `FLASK_SECRET_KEY` | random per start |

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

The project depends on exactly three third-party packages — `Flask`, `pyodbc`, and `web3` —
everything else it imports is in the standard library.

Two notes on `requirements.txt`:

- **`pyodbc` needs a system ODBC driver**, which pip does not install. On Windows the `{SQL Server}`
  driver ships with SQL Server itself. On Linux/macOS install `msodbcsql18` and set
  `DB_DRIVER="ODBC Driver 18 for SQL Server"` plus `DB_USER`/`DB_PASSWORD`.
- **`web3` is capped below v7.** The code uses the v5/v6 API; v7 reorganised parts of that surface.

### 4. Start Ganache and deploy the contracts

Launch Ganache on `127.0.0.1:7545`, then:

```bash
cd AgricultureFoodSupplyChain-Truffle
truffle compile
truffle migrate --reset
```

The app reads the new `TransactionDetailsContract` address from `build/contracts/` automatically.
`--reset` matters if you deployed before chain anchoring was added: the old contract has no
`anchorChain`, and *Generate Blocks* will say so until it is redeployed.

### 5. Hash the stored passwords

The seed database stores passwords in plain text. Hash them once:

```bash
python AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/src/upgrade_passwords.py
```

If you skip this, each password is hashed the first time its user logs in.

### 6. Run the app

```bash
python AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/src/AgricultureFoodSupplyChainV1Server.py
```

It can be started from any directory. Open <http://127.0.0.1:5000/> and log in with a user from
the `Users` table (the account must have `isActive = 1`).

## Repository Layout

```
AgroTrustChain/
├── .github/workflows/ci.yml                       # CI/CD: tests, smoke test, Vercel demo deploy
├── demo/                                          # Read-only Vercel demo (build_demo.py, vercel.json, templates/)
├── simulation/                                    # WTH-Raft simulation (wthraft/, run.py, results/, tests/)
├── docker-compose.yml                             # Full stack: db, ganache, contracts, app
├── .env.example                                   # Optional overrides for docker compose
├── docker/
│   ├── app/Dockerfile                             # Python 3.11 + ODBC Driver 18 + gunicorn
│   ├── contracts/Dockerfile, migrate.sh           # Truffle; deploys to ganache on start
│   ├── db/init.sh                                 # Restores the .bak, then runs migrate.sql
│   └── smoke-test.sh                              # End-to-end check of a running stack
│
├── AgricultureFoodSupplyChain/                    # Flask application
│   ├── AgricultureFoodSupplyChainV1DB.bak         # SQL Server database backup (restore this)
│   ├── migrate.sql                                # Idempotent schema fixes (run after restoring)
│   └── AgricultureFoodSupplyChain/
│       └── src/
│           ├── AgricultureFoodSupplyChainV1Server.py  # Flask app — all routes, login, RBAC
│           ├── HashChain.py                       # Seals, anchors and verifies the hash chain
│           ├── Blockchain.py                      # Web3 calls to both contracts
│           ├── BatchModel.py                      # DAO: Batch table (scores live on-chain)
│           ├── Passwords.py                       # Salted password hashing
│           ├── upgrade_passwords.py               # Hashes legacy plain-text passwords
│           ├── Constants.py                       # Configuration (env vars, Windows defaults)
│           ├── AgricultureBoardModel.py           # DAO: AgricultureBoard table
│           ├── BuyerModel.py                      # DAO: Buyer table
│           ├── FarmerModel.py                     # DAO: Farmer table
│           ├── ProductModel.py                    # DAO: Product table
│           ├── RoleModel.py                       # DAO: Role table (permission flags)
│           ├── UsersModel.py                      # DAO: Users table
│           ├── TransactionDetailsModel.py         # DAO; records on Ethereum before inserting
│           ├── templates/                         # Jinja2 templates
│           │   ├── Home.html                      # App shell: sidebar, user card, theme toggle
│           │   ├── _ui.html                       # Shared macros: icons, page header, fields, badges, tables
│           │   ├── Dashboard.html, Login.html, Information.html, ChangePassword.html
│           │   ├── <Entity>Listing.html           # Searchable table per entity
│           │   ├── <Entity>Operation.html         # Create / edit form, delete confirmation
│           │   ├── Batch*.html, Reputation.html   # Quality & reputation pages
│           │   └── BlockChain*.html               # Generate blocks, hash-chain report
│           └── static/
│               ├── app.css                        # Design tokens (light + dark) and components
│               ├── app.js                         # Sidebar, table search, copy buttons, theme switch
│               ├── favicon.svg
│               └── charts/, UPLOADED_FILES/       # Output/upload directories
│
├── AgricultureFoodSupplyChain-Truffle/            # Ethereum / Truffle project
│   ├── contracts/
│   │   ├── AgricultureBoardContract.sol           # Per-entity transaction recorders
│   │   ├── BuyerContract.sol
│   │   ├── FarmerContract.sol
│   │   ├── ProductContract.sol
│   │   ├── RoleContract.sol
│   │   ├── TransactionDetailsContract.sol         # Transactions + hash-chain anchor (app calls it)
│   │   ├── TraceabilityManagement.sol             # Batches, compliance, Q/R scores, penalties (app calls it)
│   │   ├── UsersContract.sol
│   │   ├── AgroCoin.sol                           # ERC20-style token (AGC, supply 1,000,000)
│   │   ├── TrustCoin.sol                          # ERC20-style token (TRC, supply 500,000)
│   │   └── Migrations.sol
│   ├── migrations/                                # Truffle deployment scripts (1–8)
│   ├── build/contracts/*.json                     # Compiled ABIs + deployed addresses
│   └── truffle-config.js                          # solc 0.8.10, dev network 127.0.0.1:7545
│
├── Research Paper.pdf                             # The research paper
├── requirements.txt                               # Python dependencies
├── .gitignore, .gitattributes, .dockerignore
├── README.md                                      # Overview
├── CONTRIBUTING.md                                # This file
├── SECURITY.md                                    # Security status and known limitations
└── LICENSE                                        # MIT
```

## Conventions

- **Line endings.** Most existing source files use CRLF, because the project was written on
  Windows. Keep each file's existing line endings so diffs stay readable. Shell scripts must be LF:
  `.gitattributes` enforces this, because CRLF breaks them inside Linux containers.
- **Reputation rules live in the contract** (`TraceabilityManagement.sol`). `simulation/wthraft/reputation.py`
  mirrors them for the simulation and the demo; a test fails if the constants drift apart, so change both together.
- **Database changes go in `migrate.sql`.** It runs on every Docker start and by hand after a
  manual restore, so every statement must be idempotent: guard with `IF NOT EXISTS` / `IF EXISTS`.
  Do not edit the `.bak`. It is the seed that everyone restores from.
- **UI building blocks.** Use the macros in `templates/_ui.html` (`page_header`, `field`, `select`, `badge`, `empty`,
  `hash`, `row_actions`, `form_footer`, `icon`) and the tokens in `static/app.css` rather than one-off styles. Colours
  come from CSS variables, so new components get the dark theme for free; never hard-code a light-only colour.
- **Forms need a CSRF token.** Every `<form method="post">` must include
  `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>`; POSTs without it get a 400.
- **Passwords go through `Passwords.py`.** Never store or compare them directly.
- **Use parameterised SQL** (`cursor.execute(sql, params)` with `?` placeholders) everywhere. Never
  build SQL by concatenating request values.
- **The hash format is a contract with existing data.** `HashChain.HASH_FIELDS` and
  `compute_block_hash()` define what a sealed block's hash covers. Changing either makes every
  previously sealed block show as *Tampered*. If you must change them, document the re-seal step
  (see "Re-sealing an old chain" in the README).
- **Seal columns belong to `HashChain`.** `isBlockChainGenerated`, `hash`, `prevHash` and
  `sequenceNumber` are written only by `HashChain.seal_pending_blocks()` and by
  `TransactionDetailsModel.insert()`, which assigns the next `sequenceNumber`. Other updates must
  leave them alone.
- **New routes** need `@login_required(...)`, with a role flag if the page belongs to a module.
- **Configuration** goes through `Constants.py` and environment variables. Don't hard-code hosts,
  passwords or contract addresses.
- **Build artifacts.** `AgricultureFoodSupplyChain-Truffle/build/` is tracked so that a manual
  setup has ABIs before the first migrate. Commit changes there only when a contract's interface
  changes.
- **Secrets.** Never commit `.env`, private keys or mnemonics (`.gitignore` covers the usual names).

## Tests

```bash
docker compose run --rm tests                      # Python: hash chain, passwords, login, CSRF, permissions
docker compose run --rm contracts truffle test     # Solidity: both contracts, against Ganache
python -m pytest simulation/tests                  # WTH-Raft simulation (pip install -r simulation/requirements.txt pytest)
```

- **Python** (`AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/tests/`, pytest). These need
  no database or chain: the hash-chain logic lives in pure functions (`plan_seal`, `check_blocks`),
  and the web tests run the real Flask app against a fake `pyodbc` connection (see `conftest.py`).
  Outside Docker: `pip install pytest`, then `python -m pytest AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/tests`
  (pyodbc still needs the system ODBC library to import).
- **Solidity** (`AgricultureFoodSupplyChain-Truffle/test/`). Outside Docker: start Ganache, then
  `truffle test` in `AgricultureFoodSupplyChain-Truffle`.

`bash docker/smoke-test.sh` checks a running stack end to end: it logs in, records a transaction
on Ethereum, seals it, confirms the report and anchor, then tampers with the record and confirms
that is detected.

Add a test with every change to `HashChain.py`, the login flow or the contract.

## CI/CD and the Vercel Demo

`.github/workflows/ci.yml` runs on every pull request and every push to `main`:

| Job | What it does |
| --- | --- |
| Python tests | `docker compose run --rm tests` |
| Contract tests | `truffle test` against Ganache |
| Full-stack smoke test | Starts the whole Docker stack and runs `docker/smoke-test.sh` |
| WTH-Raft simulation | Simulation tests and a `--quick` run (results uploaded as an artifact) |
| Build Vercel demo | `python demo/build_demo.py` |
| Deploy preview | Pull requests only, after all of the above pass: an automatic Vercel **preview** |
| Deploy production | `main` only, after all of the above pass: waits for **manual approval**, then deploys to <https://agrotrustchain.vercel.app> |

**Approving a production deploy.** Production runs in the GitHub `production` environment
(*Settings → Environments*). It may only deploy from `main` and needs approval from a required
reviewer. After a merge, open the run under *Actions* and choose **Review deployments → Approve and
deploy**. Rejecting it, or leaving it for 30 days, leaves production unchanged.

**The demo** ([demo/build_demo.py](demo/build_demo.py)) is a static, read-only site. Vercel can't
host SQL Server or Ganache, so the app's templates are rendered with fictional sample data. The
Blockchain Report pages are computed with `HashChain`'s real functions, and forms are disabled. To
build it locally: `pip install jinja2 && python demo/build_demo.py`, then open `demo/dist/`.

**Deployment secrets.** The deploy jobs need three repository secrets. Without them they skip
the deploy and the other jobs still run.

| Secret | Value |
| --- | --- |
| `VERCEL_TOKEN` | A Vercel token, ideally scoped to the project: `vercel tokens create "AgroTrustChain CI" --project agrotrustchain` |
| `VERCEL_ORG_ID` | `orgId` from `.vercel/project.json` after `vercel link` |
| `VERCEL_PROJECT_ID` | `projectId` from the same file |

The Vercel project is deliberately **not** connected to the Git repository. Vercel's own Git
integration would deploy the repository root, which is the raw source and the `.bak` database,
without waiting for the tests. Deploys go only through this workflow.

## Known Gaps

Contributions are welcome in these areas. For security-related gaps, see [SECURITY.md](SECURITY.md).

- **No end-to-end tests.** The suites above cover the logic and the contract, but nothing drives
  the full Docker stack (database, chain and app together) automatically. Such checks are done by
  hand today.
- **Contract duplication.** The seven entity contracts are identical apart from their names; a
  single parameterised contract would serve.
- **The reputation engine trusts its inspector.** Inspection results are entered by app users
  with the `canFarmer` permission and sent from the app's account. The contract cannot tell a
  wrong inspection from a dishonest farmer. The simulation's Byzantine results likewise assume
  the inspection reveals the truth after every round.
- **Scores are keyed by farmer ID strings.** Suppliers have no Ethereum accounts of their own; the
  app acts for everyone. Giving each farmer a wallet would let them sign their own claims.
- **Sealing holds table locks while anchoring.** *Generate Blocks* keeps the `TransactionDetails`
  locks until the Ethereum anchor is confirmed. That takes milliseconds on Ganache, but would block
  other users for the block time on a real network.
- **Manual setup is Windows-first.** The default connection string uses the `{SQL Server}` driver
  with Integrated Security. On other systems use Docker, or set the `DB_*` environment variables.
- **Truffle is sunset upstream.** It still works (the Docker image pins 5.11.5), but a move to
  Hardhat or Foundry would be the long-term path.

## Submitting Changes

1. Create a branch from `main`.
2. Make your change, add or update tests, and run both suites (see [Tests](#tests)).
3. Check it in the Docker stack: log in, exercise the pages you touched, and for anything near the
   chain, run *Generate Blocks* and open the *Blockchain Report*.
4. Open a pull request that explains what changed and how you checked it.
