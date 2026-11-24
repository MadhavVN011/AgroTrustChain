#!/usr/bin/env bash
# Deploys the contracts to Ganache and writes the artifacts (ABI + address) to
# $CONTRACTS_BUILD_DIR, where the Flask app reads them.
set -euo pipefail

echo "Waiting for Ganache at $GANACHE_HOST:$GANACHE_PORT ..."
for _ in $(seq 1 60); do
    if node -e "require('http').request({host:process.env.GANACHE_HOST,port:process.env.GANACHE_PORT,method:'POST',headers:{'content-type':'application/json'}},r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1)).end('{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"net_version\",\"params\":[]}')"; then
        break
    fi
    sleep 2
done

# Normal case: deploy only migrations that have not run yet. If the chain was
# wiped but the artifacts were kept (or the other way round), redeploy all.
if ! truffle migrate --network development; then
    echo "Incremental migrate failed; redeploying everything with --reset ..."
    truffle migrate --network development --reset
fi
