# Contributing to AgroTrustChain

This guide covers the development setup and the conventions the code relies on. For an overview
of what the system does, see the [README](README.md).

## Contents

1. [Development with Docker](#development-with-docker)
2. [Running Without Docker (Windows)](#running-without-docker-windows)
3. [Repository Layout](#repository-layout)
4. [Conventions](#conventions)
5. [Known Gaps](#known-gaps)
6. [Submitting Changes](#submitting-changes)

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

### 5. Run the app

```bash
python AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/src/AgricultureFoodSupplyChainV1Server.py
```

It can be started from any directory. Open <http://127.0.0.1:5000/> and log in with a user from
the `Users` table (the account must have `isActive = 1`).

## Repository Layout

```
AgroTrustChain/
├── docker-compose.yml                             # Full stack: db, ganache, contracts, app
├── .env.example                                   # Optional overrides for docker compose
├── docker/
│   ├── app/Dockerfile                             # Python 3.11 + ODBC Driver 18 + gunicorn
│   ├── contracts/Dockerfile, migrate.sh           # Truffle; deploys to ganache on start
│   └── db/init.sh                                 # Restores the .bak, then runs migrate.sql
│
├── AgricultureFoodSupplyChain/                    # Flask application
│   ├── AgricultureFoodSupplyChainV1DB.bak         # SQL Server database backup (restore this)
│   ├── migrate.sql                                # Idempotent schema fixes (run after restoring)
│   └── AgricultureFoodSupplyChain/
│       └── src/
│           ├── AgricultureFoodSupplyChainV1Server.py  # Flask app — all routes, login, RBAC
│           ├── HashChain.py                       # Seals and verifies the hash chain
│           ├── Constants.py                       # Configuration (env vars, Windows defaults)
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
- **Database changes go in `migrate.sql`.** It runs on every Docker start and by hand after a
  manual restore, so every statement must be idempotent: guard with `IF NOT EXISTS` / `IF EXISTS`.
  Do not edit the `.bak`. It is the seed that everyone restores from.
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

## Known Gaps

Contributions are welcome in these areas. For security-related gaps, see [SECURITY.md](SECURITY.md).

- **No automated tests.** `AgricultureFoodSupplyChain-Truffle/test/` is empty and there are no
  Python tests. `HashChain` (sealing and verification) and the contracts are the most valuable
  places to start.
- **Contract duplication.** The seven entity contracts are identical apart from their names; a
  single parameterised contract would serve.
- **Duplicate migration number.** `3_buyer_migration.js` and `3_deploy_tokens.js` share the prefix
  `3`. Truffle runs both, but renumbering would make the order explicit.
- **Database before chain.** `TransactionDetailsModel.insert()` commits the SQL row before sending
  the Ethereum transaction. If Ganache is unreachable, the row stays without an on-chain record,
  and the Ethereum transaction hash is not stored anywhere.
- **Manual setup is Windows-first.** The default connection string uses the `{SQL Server}` driver
  with Integrated Security. On other systems use Docker, or set the `DB_*` environment variables.
- **Truffle is sunset upstream.** It still works (the Docker image pins 5.11.5), but a move to
  Hardhat or Foundry would be the long-term path.

## Submitting Changes

1. Create a branch from `main`.
2. Make your change and check it in the Docker stack: log in, exercise the pages you touched, and
   for anything near the chain, run *Generate Blocks* and open the *Blockchain Report*.
3. Open a pull request that explains what changed and how you checked it.
