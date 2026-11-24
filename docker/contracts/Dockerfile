FROM node:18-bookworm-slim

# Truffle is sunset upstream but still installs and works; 5.11.5 is its final release.
RUN npm install -g truffle@5.11.5 --no-audit --no-fund \
    && npm cache clean --force

WORKDIR /truffle
COPY AgricultureFoodSupplyChain-Truffle/contracts ./contracts
COPY AgricultureFoodSupplyChain-Truffle/migrations ./migrations
COPY AgricultureFoodSupplyChain-Truffle/truffle-config.js ./truffle-config.js
COPY docker/contracts/migrate.sh /usr/local/bin/migrate.sh

# Compile once at build time so the solc 0.8.10 download is cached in the image.
RUN truffle compile --contracts_build_directory /tmp/precompiled && rm -rf /tmp/precompiled

CMD ["bash", "/usr/local/bin/migrate.sh"]
