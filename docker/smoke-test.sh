#!/usr/bin/env bash
# End-to-end check of a running Docker stack (`docker compose up -d --build`):
# log in, create a transaction (recorded on Ethereum), seal it, and confirm the
# Blockchain Report verifies the chain and its Ethereum anchor.
#
#   bash docker/smoke-test.sh [base-url]
set -euo pipefail

BASE="${1:-http://127.0.0.1:${APP_PORT:-5000}}"
JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
token() {  # CSRF token from a page
    curl -fsS -b "$JAR" -c "$JAR" "$BASE/$1" | grep -o 'name="csrf_token" value="[^"]*"' | head -1 | sed 's/.*value="//; s/"$//'
}
sql() {
    docker compose exec -T db /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "${MSSQL_SA_PASSWORD:-AgroTrust_Dev_2026!}" \
        -d AgricultureFoodSupplyChainV1 -h -1 -W -s '|' -Q "SET NOCOUNT ON; $1"
}

echo "Waiting for $BASE ..."
for _ in $(seq 1 90); do
    curl -fsS -o /dev/null "$BASE/" 2>/dev/null && break
    sleep 2
done
curl -fsS -o /dev/null "$BASE/" || fail "app did not come up"

echo "Logged-out access is redirected"
[ "$(curl -s -o /dev/null -w '%{redirect_url}' "$BASE/BlockChainReport")" = "$BASE/" ] || fail "report reachable without login"

echo "POST without CSRF token is rejected"
[ "$(curl -s -o /dev/null -w '%{http_code}' -d emailid=1@1.com -d password=1 "$BASE/processLogin")" = "400" ] || fail "CSRF not enforced"

echo "Log in with the seeded account"
[ "$(curl -s -b "$JAR" -c "$JAR" -o /dev/null -w '%{redirect_url}' -d emailid=1@1.com -d password=1 \
     -d csrf_token="$(token "")" "$BASE/processLogin")" = "$BASE/Dashboard" ] || fail "login failed"

echo "Create a transaction"
IFS='|' read -r AB BU FA PR <<<"$(sql "SELECT (SELECT TOP 1 agricultureBoardID FROM AgricultureBoard)+'|'+(SELECT TOP 1 buyerID FROM Buyer)+'|'+(SELECT TOP 1 farmerID FROM Farmer)+'|'+(SELECT TOP 1 productID FROM Product)")"
curl -fsS -b "$JAR" -c "$JAR" -o /dev/null -F csrf_token="$(token "TransactionDetailsOperation?operation=Create")" \
    -F operation=Create -F orderID= -F agricultureBoardID="$AB" -F gstNbr=GST-SMOKE -F buyerID="$BU" -F farmerID="$FA" \
    -F effDate=2026-01-01 -F productID="$PR" -F price=10 -F qty=2 "$BASE/ProcessTransactionDetailsOperation"
ETH_TX="$(sql "SELECT ethTxHash FROM TransactionDetails WHERE gstNbr='GST-SMOKE'")"
[[ "$ETH_TX" =~ ^0x[0-9a-f]{64}$ ]] || fail "transaction not recorded on Ethereum (ethTxHash='$ETH_TX')"

echo "Seal pending transactions"
curl -fsS -b "$JAR" -c "$JAR" -X POST -d csrf_token="$(token BlockChainGeneration)" "$BASE/ProcessBlockchainGeneration" \
    | grep -q 'were sealed' || fail "sealing failed"

echo "Blockchain Report verifies the chain and its Ethereum anchor"
REPORT="$(curl -fsS -b "$JAR" "$BASE/BlockChainReport")"
grep -q 'Chain intact' <<<"$REPORT" || fail "chain not reported intact"
grep -q 'matches the anchor on Ethereum' <<<"$REPORT" || fail "anchor not confirmed"

echo "Tampering with a sealed record is detected"
sql "UPDATE TransactionDetails SET qty = qty + 1 WHERE gstNbr='GST-SMOKE'" >/dev/null
curl -fsS -b "$JAR" "$BASE/BlockChainReport" | grep -q 'Tampering detected' || fail "tampering not detected"

echo "Smoke test passed."
