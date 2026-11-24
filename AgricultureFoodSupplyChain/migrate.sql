-- AgroTrustChain schema fixes for AgricultureFoodSupplyChainV1.
--
-- Safe to run any number of times: Docker runs it on every start. To apply it
-- to a database restored by hand, open it in SSMS against
-- AgricultureFoodSupplyChainV1, or run:
--     sqlcmd -S <server> -d AgricultureFoodSupplyChainV1 -i migrate.sql

SET NOCOUNT ON;

-- 1. Older versions of the app inserted every transaction with
--    sequenceNumber = 0. The hash chain is ordered by sequenceNumber, so give
--    each unsealed transaction a unique number after the last sealed block.
--    Sealed rows are left alone: their sequenceNumber is part of their hash.
IF EXISTS (SELECT sequenceNumber FROM TransactionDetails GROUP BY sequenceNumber HAVING COUNT(*) > 1)
BEGIN
    DECLARE @lastSealed int = ISNULL((SELECT MAX(sequenceNumber) FROM TransactionDetails WHERE isBlockChainGenerated = 1), 0);

    WITH pending AS (
        SELECT sequenceNumber,
               ROW_NUMBER() OVER (ORDER BY sequenceNumber, effDate, orderID) AS rn
        FROM TransactionDetails
        WHERE ISNULL(isBlockChainGenerated, 0) = 0
    )
    UPDATE pending SET sequenceNumber = @lastSealed + rn;

    PRINT 'Renumbered unsealed transactions after sequenceNumber ' + CAST(@lastSealed AS varchar(20)) + '.';
END;

-- 2. Enforce unique sequence numbers from now on.
IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = 'UX_TransactionDetails_sequenceNumber'
                 AND object_id = OBJECT_ID('dbo.TransactionDetails'))
BEGIN
    IF EXISTS (SELECT sequenceNumber FROM TransactionDetails GROUP BY sequenceNumber HAVING COUNT(*) > 1)
        PRINT 'WARNING: sealed transactions share sequence numbers, so the unique index was not created. '
            + 'They were sealed by an older version of the app; see "Re-sealing an old chain" in README.md.';
    ELSE
    BEGIN
        CREATE UNIQUE INDEX UX_TransactionDetails_sequenceNumber ON dbo.TransactionDetails (sequenceNumber);
        PRINT 'Created unique index UX_TransactionDetails_sequenceNumber.';
    END;
END;

-- 3. Store the Ethereum transaction hash recorded for each transaction.
IF COL_LENGTH('dbo.TransactionDetails', 'ethTxHash') IS NULL
BEGIN
    ALTER TABLE dbo.TransactionDetails ADD ethTxHash nvarchar(66) NULL;
    PRINT 'Added column TransactionDetails.ethTxHash.';
END;

-- 4. Make room for salted password hashes (about 160 characters). The app
--    hashes any remaining plain-text passwords (upgrade_passwords.py).
IF COL_LENGTH('dbo.Users', 'password') < 510   -- nvarchar length is in bytes
BEGIN
    ALTER TABLE dbo.Users ALTER COLUMN password nvarchar(255) NULL;
    PRINT 'Widened Users.password to nvarchar(255).';
END;

-- 5. Product batches with their certificates and quality inspections. The
--    scores and penalties live on-chain in TraceabilityManagement; this table
--    keeps the batch details for listing.
IF OBJECT_ID('dbo.Batch', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Batch (
        batchID            nvarchar(100) NOT NULL CONSTRAINT PK_Batch PRIMARY KEY,
        farmerID           nvarchar(100) NOT NULL,
        productID          nvarchar(100) NULL,
        certificateNumber  nvarchar(200) NOT NULL,
        certificateHash    nvarchar(64)  NOT NULL,
        certificateExpiry  date          NOT NULL,
        claimedQuality     int           NOT NULL,
        inspectedQuality   int           NULL,
        status             nvarchar(30)  NOT NULL,
        ethTxHash          nvarchar(66)  NULL,
        inspectionTxHash   nvarchar(66)  NULL,
        createdAt          datetime2     NOT NULL CONSTRAINT DF_Batch_createdAt DEFAULT SYSUTCDATETIME()
    );
    PRINT 'Created table Batch.';
END;
