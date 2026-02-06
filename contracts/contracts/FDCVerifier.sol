// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./interfaces/IFdcVerification.sol";
import "./interfaces/IFdcHub.sol";
import "./interfaces/IFlareContractRegistry.sol";

/**
 * @title FDCVerifier
 * @notice Verifies Flare Data Connector attestation proofs for external data.
 *
 *         Primary use-case: escrow release is gated on an FDC-attested
 *         "delivery status" from a Web2 API — making the release trustless.
 *
 *         The contract stores verified delivery confirmations per job ID,
 *         which FlareEscrow checks before releasing funds.
 */
contract FDCVerifier is Ownable {
    /// @dev Flare Contract Registry (same address on Coston2 & mainnet)
    address public constant FLARE_CONTRACT_REGISTRY =
        0xaD67FE66660Fb8dFE9d6b1b4240d8650e30F6019;

    /// @dev Attestation type hash for JSON-API requests
    bytes32 public constant JSON_API_ATTESTATION_TYPE =
        keccak256("IJsonApi");

    /// @dev FDC verification contract (resolved from registry or set manually)
    IFdcVerification public fdcVerification;

    /// @dev FDC Hub for requesting attestations
    IFdcHub public fdcHub;

    /// @dev jobId => whether delivery has been attested as complete
    mapping(uint256 => bool) public deliveryConfirmed;

    /// @dev jobId => attestation proof hash (for audit trail)
    mapping(uint256 => bytes32) public attestationHashes;

    /// @dev Authorised callers that can submit attestation proofs (e.g. agents)
    mapping(address => bool) public authorisedSubmitters;

    event FdcVerificationSet(address indexed verifier);
    event FdcHubSet(address indexed hub);
    event DeliveryAttested(
        uint256 indexed jobId,
        bytes32 proofHash,
        address indexed submitter
    );
    event SubmitterAuthorised(address indexed submitter, bool authorised);

    modifier onlyAuthorised() {
        require(
            authorisedSubmitters[msg.sender] || msg.sender == owner(),
            "FDCVerifier: not authorised"
        );
        _;
    }

    constructor(address initialOwner) Ownable(initialOwner) {
        _resolveFdcContracts();
    }

    // ─── Configuration ──────────────────────────────────────

    function resolveFdcContracts() external onlyOwner {
        _resolveFdcContracts();
    }

    function setFdcVerification(address verifier) external onlyOwner {
        fdcVerification = IFdcVerification(verifier);
        emit FdcVerificationSet(verifier);
    }

    function setFdcHub(address hub) external onlyOwner {
        fdcHub = IFdcHub(hub);
        emit FdcHubSet(hub);
    }

    function setSubmitterAuthorised(
        address submitter,
        bool authorised
    ) external onlyOwner {
        authorisedSubmitters[submitter] = authorised;
        emit SubmitterAuthorised(submitter, authorised);
    }

    // ─── Attestation Request ────────────────────────────────

    /**
     * @notice Request an FDC attestation for a job's delivery status.
     * @param attestationData  ABI-encoded attestation request
     *                         (built off-chain by the agent).
     * @return requestId  The FDC request identifier.
     */
    function requestDeliveryAttestation(
        bytes calldata attestationData
    ) external payable onlyAuthorised returns (bytes32 requestId) {
        require(address(fdcHub) != address(0), "FDCVerifier: hub not set");
        requestId = fdcHub.requestAttestation{value: msg.value}(
            attestationData
        );
    }

    // ─── Attestation Verification ───────────────────────────

    /**
     * @notice Submit and verify an FDC proof that delivery is complete.
     *         The proof's response body must ABI-encode to (uint256 jobId, bool delivered).
     *
     * @dev This is the KEY integration point for the Flare BONUS bounty:
     *      escrow release is driven entirely by FDC-attested external data,
     *      not by a trusted backend.
     *
     * @param jobId  The on-chain job ID.
     * @param proof  The FDC Merkle proof for the Web2 JSON API attestation.
     */
    function verifyDelivery(
        uint256 jobId,
        IJsonApi.Proof calldata proof
    ) external onlyAuthorised {
        require(!deliveryConfirmed[jobId], "FDCVerifier: already confirmed");
        require(
            address(fdcVerification) != address(0),
            "FDCVerifier: verifier not set"
        );

        // Verify the Merkle proof against the FDC relay
        bool valid = fdcVerification.verifyJsonApi(proof);
        require(valid, "FDCVerifier: invalid proof");

        // Decode the response: expect (uint256 _jobId, bool _delivered)
        (uint256 attestedJobId, bool delivered) = abi.decode(
            proof.body.responseBody.abiEncodedData,
            (uint256, bool)
        );
        require(attestedJobId == jobId, "FDCVerifier: job ID mismatch");
        require(delivered, "FDCVerifier: delivery not confirmed");

        deliveryConfirmed[jobId] = true;
        attestationHashes[jobId] = keccak256(abi.encode(proof));

        emit DeliveryAttested(
            jobId,
            attestationHashes[jobId],
            msg.sender
        );
    }

    /**
     * @notice For local/test environments: manually confirm delivery.
     *         This bypasses FDC verification. ONLY available to the owner.
     */
    function manualConfirmDelivery(uint256 jobId) external onlyOwner {
        require(!deliveryConfirmed[jobId], "FDCVerifier: already confirmed");
        deliveryConfirmed[jobId] = true;
        attestationHashes[jobId] = bytes32(0);
        emit DeliveryAttested(jobId, bytes32(0), msg.sender);
    }

    // ─── View ───────────────────────────────────────────────

    function isDeliveryConfirmed(uint256 jobId) external view returns (bool) {
        return deliveryConfirmed[jobId];
    }

    // ─── Internals ──────────────────────────────────────────

    function _resolveFdcContracts() internal {
        if (FLARE_CONTRACT_REGISTRY.code.length == 0) return;

        IFlareContractRegistry registry = IFlareContractRegistry(
            FLARE_CONTRACT_REGISTRY
        );

        address verifier = registry.getContractAddressByName(
            "FdcVerification"
        );
        if (verifier != address(0)) {
            fdcVerification = IFdcVerification(verifier);
            emit FdcVerificationSet(verifier);
        }

        address hub = registry.getContractAddressByName("FdcHub");
        if (hub != address(0)) {
            fdcHub = IFdcHub(hub);
            emit FdcHubSet(hub);
        }
    }
}
