// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title IFdcVerification
 * @notice Minimal interface for verifying FDC attestation proofs on-chain.
 *         The relay contract on Flare stores Merkle roots; we verify against them.
 */
interface IFdcVerification {
    /**
     * @notice Verify that a Web2 JSON-API attestation proof is valid.
     * @param proof The Merkle proof structure for a Web2Json attestation.
     * @return True if the proof is valid against a confirmed Merkle root.
     */
    function verifyJsonApi(
        IJsonApi.Proof calldata proof
    ) external view returns (bool);
}

/**
 * @title IJsonApi
 * @notice Attestation type structures for FDC Web2 JSON API attestations.
 */
interface IJsonApi {
    struct Proof {
        bytes32[] merkleProof;
        Body body;
    }

    struct Body {
        bytes32 attestationType;
        bytes32 sourceId;
        uint64 votingRound;
        uint64 lowestUsedTimestamp;
        Request requestBody;
        Response responseBody;
    }

    struct Request {
        string url;
        string postprocessJq;
        string headerKey;
        string headerValue;
    }

    struct Response {
        bytes abiEncodedData;
    }
}
