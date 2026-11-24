#!/usr/bin/env bash
# Restores AgricultureFoodSupplyChainV1 from the checked-in .bak the first time
# the stack starts, then applies migrate.sql (idempotent) on every start.
set -euo pipefail

DB_NAME="${DB_NAME:-AgricultureFoodSupplyChainV1}"
BACKUP="/backup/AgricultureFoodSupplyChainV1DB.bak"   # path inside the db container
SQLCMD=(/opt/mssql-tools18/bin/sqlcmd -C -b -S "${DB_HOST:-db}" -U sa -P "$MSSQL_SA_PASSWORD")

exists=$("${SQLCMD[@]}" -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.databases WHERE name = N'$DB_NAME'")

if [ "$(echo "$exists" | tr -d '[:space:]')" = "0" ]; then
    echo "Restoring $DB_NAME from $BACKUP ..."
    # The backup was taken on Windows, so its files must be moved to Linux paths.
    "${SQLCMD[@]}" -Q "RESTORE DATABASE [$DB_NAME] FROM DISK = N'$BACKUP'
        WITH MOVE N'AgricultureFoodSupplyChainV1'     TO N'/var/opt/mssql/data/$DB_NAME.mdf',
             MOVE N'AgricultureFoodSupplyChainV1_log' TO N'/var/opt/mssql/data/${DB_NAME}_log.ldf',
             RECOVERY"
else
    echo "$DB_NAME already exists; skipping restore."
fi

# After a restart, SQL Server accepts logins (and even reports the database as
# ONLINE) before user databases finish starting up. Retry until it opens.
for _ in $(seq 1 60); do
    "${SQLCMD[@]}" -d "$DB_NAME" -Q "SELECT 1" >/dev/null 2>&1 && break
    echo "Waiting for $DB_NAME to finish starting up ..."
    sleep 2
done

echo "Applying migrate.sql ..."
"${SQLCMD[@]}" -d "$DB_NAME" -i /scripts/migrate.sql
echo "Database ready."
