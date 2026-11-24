// SPDX-License-Identifier: MIT
pragma solidity >=0.8.10 <0.9.0;

/// Batch registry, compliance checks and the hybrid reputation-quality engine
/// described in the AgroTrustChain paper (Fig. 1: RegisterBatch, UpdateQuality,
/// RevokeCertificate; on-chain reputation indexing, off-chain quality
/// validation, automated penalty deduction).
///
/// Every supplier (farmer) has two scores from 0 to 100:
///   Q-Score: quality of its products, as found by off-chain inspection
///   R-Score: reputation, i.e. its history of reporting honestly
/// and a consensus weight W = (alpha * Q + beta * R) / 100, the paper's
/// "R = aQ + bS" weight apportionment.
///
/// The paper does not give numeric values for the weights, rewards or
/// penalties. The defaults below are this implementation's choices and can be
/// changed by the owner with setParameters().
contract TraceabilityManagement {
    uint8 public constant MAX_SCORE = 100;

    address public owner;

    uint8 public alpha = 50;              // weight of Q-Score in W (percent)
    uint8 public beta = 50;               // weight of R-Score in W (percent); alpha + beta == 100
    uint8 public initialQuality = 50;     // Q-Score of a new supplier
    uint8 public initialReputation = 50;  // R-Score of a new supplier
    uint8 public honestReward = 2;        // R-Score gained per consistent quality report
    uint8 public penalty = 20;            // R-Score lost per inconsistent quality report
    uint8 public tolerance = 10;          // largest |claimed - inspected| still counted as consistent
    uint8 public minQuality = 40;         // quality criterion a batch must meet
    uint8 public suspendBelow = 20;       // an R-Score below this suspends the supplier

    struct Supplier {
        bool registered;
        bool suspended;
        uint8 qualityScore;
        uint8 reputationScore;
        uint32 batches;
        uint32 penalties;
    }

    enum BatchStatus { None, Pending, Validated, Revoked }

    struct Batch {
        string supplierId;
        bytes32 certificateHash;
        uint64 certificateExpiry;   // unix seconds
        uint8 claimedQuality;
        uint8 inspectedQuality;
        BatchStatus status;
    }

    mapping(string => Supplier) public suppliers;
    mapping(string => Batch) public batches;
    mapping(bytes32 => bool) public revokedCertificates;

    event SupplierRegistered(string supplierId);
    event BatchRegistered(string batchId, string supplierId, bytes32 certificateHash, uint8 claimedQuality);
    event QualityValidated(string batchId, string supplierId, uint8 claimedQuality, uint8 inspectedQuality, bool consistent);
    event PenaltyApplied(string supplierId, uint8 amount, uint8 newReputationScore);
    event BatchRevoked(string batchId, string reason);
    event SupplierSuspended(string supplierId);
    event SupplierReinstated(string supplierId);
    event CertificateRevoked(bytes32 certificateHash);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only the owner can do this");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    // ------------------------------------------------------------------
    // Suppliers
    // ------------------------------------------------------------------

    function registerSupplier(string memory supplierId) public onlyOwner {
        require(!suppliers[supplierId].registered, "Supplier already registered");
        _register(supplierId);
    }

    function _register(string memory supplierId) private {
        Supplier storage s = suppliers[supplierId];
        s.registered = true;
        s.qualityScore = initialQuality;
        s.reputationScore = initialReputation;
        emit SupplierRegistered(supplierId);
    }

    /// Consensus weight W = (alpha * Q + beta * R) / 100. Zero while suspended.
    function weightOf(string memory supplierId) public view returns (uint8) {
        Supplier storage s = suppliers[supplierId];
        if (!s.registered || s.suspended) {
            return s.registered ? 0 : uint8((uint(alpha) * initialQuality + uint(beta) * initialReputation) / 100);
        }
        return uint8((uint(alpha) * s.qualityScore + uint(beta) * s.reputationScore) / 100);
    }

    /// Whether the supplier may take part in transactions. Unregistered suppliers are eligible.
    function isEligible(string memory supplierId) public view returns (bool) {
        return !suppliers[supplierId].suspended;
    }

    /// Lift a suspension (e.g. after an appeal). The R-Score is raised to the suspension threshold.
    function reinstateSupplier(string memory supplierId) public onlyOwner {
        Supplier storage s = suppliers[supplierId];
        require(s.suspended, "Supplier is not suspended");
        s.suspended = false;
        if (s.reputationScore < suspendBelow) {
            s.reputationScore = suspendBelow;
        }
        emit SupplierReinstated(supplierId);
    }

    // ------------------------------------------------------------------
    // Batches and compliance
    // ------------------------------------------------------------------

    /// RegisterBatch: admits a batch only if it passes the compliance checks.
    function registerBatch(
        string memory batchId,
        string memory supplierId,
        bytes32 certificateHash,
        uint64 certificateExpiry,
        uint8 claimedQuality
    ) public onlyOwner {
        require(bytes(batchId).length > 0, "Batch ID required");
        require(batches[batchId].status == BatchStatus.None, "Batch already registered");
        if (!suppliers[supplierId].registered) {
            _register(supplierId);
        }
        Supplier storage s = suppliers[supplierId];
        require(!s.suspended, "Supplier is suspended");
        require(certificateHash != bytes32(0), "Certificate hash required");
        require(!revokedCertificates[certificateHash], "Certificate has been revoked");
        require(certificateExpiry > block.timestamp, "Certificate has expired");
        require(claimedQuality <= MAX_SCORE, "Quality must be 0-100");
        require(claimedQuality >= minQuality, "Claimed quality is below the minimum");

        batches[batchId] = Batch(supplierId, certificateHash, certificateExpiry, claimedQuality, 0, BatchStatus.Pending);
        s.batches += 1;
        emit BatchRegistered(batchId, supplierId, certificateHash, claimedQuality);
    }

    /// UpdateQuality: records the off-chain inspection result and applies the
    /// reputation rules. A report that disagrees with the inspection by more
    /// than `tolerance` is inconsistent: the batch is revoked, the supplier's
    /// R-Score is cut by `penalty`, and below `suspendBelow` the supplier is
    /// suspended from further transactions.
    function updateQuality(string memory batchId, uint8 inspectedQuality) public onlyOwner {
        Batch storage b = batches[batchId];
        require(b.status == BatchStatus.Pending, "Batch is not awaiting inspection");
        require(inspectedQuality <= MAX_SCORE, "Quality must be 0-100");

        Supplier storage s = suppliers[b.supplierId];
        b.inspectedQuality = inspectedQuality;

        // Q-Score: exponential moving average of inspected quality (weight 0.3 on the newest).
        s.qualityScore = uint8((uint(s.qualityScore) * 7 + uint(inspectedQuality) * 3) / 10);

        uint8 difference = b.claimedQuality > inspectedQuality
            ? b.claimedQuality - inspectedQuality
            : inspectedQuality - b.claimedQuality;
        bool consistent = difference <= tolerance;
        emit QualityValidated(batchId, b.supplierId, b.claimedQuality, inspectedQuality, consistent);

        if (consistent) {
            uint reputation = uint(s.reputationScore) + honestReward;
            s.reputationScore = reputation > MAX_SCORE ? MAX_SCORE : uint8(reputation);
            if (inspectedQuality >= minQuality) {
                b.status = BatchStatus.Validated;
            } else {
                b.status = BatchStatus.Revoked;
                emit BatchRevoked(batchId, "Inspected quality is below the minimum");
            }
            return;
        }

        s.reputationScore = s.reputationScore > penalty ? s.reputationScore - penalty : 0;
        s.penalties += 1;
        b.status = BatchStatus.Revoked;
        emit PenaltyApplied(b.supplierId, penalty, s.reputationScore);
        emit BatchRevoked(batchId, "Inconsistent quality data");
        if (s.reputationScore < suspendBelow && !s.suspended) {
            s.suspended = true;
            emit SupplierSuspended(b.supplierId);
        }
    }

    /// RevokeCertificate: no new batch can use it, and batches that did are no longer valid.
    function revokeCertificate(bytes32 certificateHash) public onlyOwner {
        require(!revokedCertificates[certificateHash], "Certificate already revoked");
        revokedCertificates[certificateHash] = true;
        emit CertificateRevoked(certificateHash);
    }

    /// A batch is valid if it passed inspection and its certificate is unrevoked and unexpired.
    function isBatchValid(string memory batchId) public view returns (bool) {
        Batch storage b = batches[batchId];
        return b.status == BatchStatus.Validated
            && !revokedCertificates[b.certificateHash]
            && b.certificateExpiry > block.timestamp;
    }

    // ------------------------------------------------------------------
    // Parameters
    // ------------------------------------------------------------------

    function setParameters(
        uint8 _alpha,
        uint8 _beta,
        uint8 _honestReward,
        uint8 _penalty,
        uint8 _tolerance,
        uint8 _minQuality,
        uint8 _suspendBelow
    ) public onlyOwner {
        require(uint(_alpha) + _beta == 100, "alpha + beta must equal 100");
        require(_tolerance <= MAX_SCORE && _minQuality <= MAX_SCORE && _suspendBelow <= MAX_SCORE, "Values must be 0-100");
        alpha = _alpha;
        beta = _beta;
        honestReward = _honestReward;
        penalty = _penalty;
        tolerance = _tolerance;
        minQuality = _minQuality;
        suspendBelow = _suspendBelow;
    }
}
