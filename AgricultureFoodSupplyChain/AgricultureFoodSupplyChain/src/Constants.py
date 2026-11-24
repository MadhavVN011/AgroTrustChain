"""Runtime configuration.

Every value can be overridden with an environment variable, which is how the
Docker setup configures the app. With no environment variables set, the
defaults reproduce the original Windows setup (local SQL Server Express with
Integrated Security, Ganache on localhost:7545).
"""
import os

serverName = os.environ.get("DB_SERVER", r"MADHAVNAIRPC\SQLEXPRESS")
databaseName = os.environ.get("DB_NAME", "AgricultureFoodSupplyChainV1")

_driver = os.environ.get("DB_DRIVER", "SQL Server")
_user = os.environ.get("DB_USER")

if _user:
    # SQL authentication (used by Docker). Braces quote the password so that
    # characters such as ';' cannot break the connection string.
    _password = os.environ.get("DB_PASSWORD", "").replace("}", "}}")
    connString = (
        "Driver={" + _driver + "};Server=" + serverName + ";Database=" + databaseName
        + ";UID=" + _user + ";PWD={" + _password + "};TrustServerCertificate=yes"
    )
else:
    # Windows Integrated Security (original setup).
    connString = "Driver={" + _driver + "};Server=" + serverName + ";Integrated_Security=true;Database=" + databaseName

# Ethereum JSON-RPC endpoint (Ganache).
eth_rpc_url = os.environ.get("ETH_RPC_URL", "http://localhost:7545")

# Folder holding Truffle's compiled artifacts (build/contracts/*.json).
contracts_build_dir = os.environ.get(
    "CONTRACTS_BUILD_DIR",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "AgricultureFoodSupplyChain-Truffle", "build", "contracts",
    )),
)

# Optional override. When unset, the TransactionDetailsContract address is read
# from the Truffle artifact for whichever network Ganache reports, so it no
# longer has to be copied by hand after every `truffle migrate`.
contract_address = os.environ.get("CONTRACT_ADDRESS") or None
