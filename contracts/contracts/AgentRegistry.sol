// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";

contract AgentRegistry is Ownable {
    enum Status {
        Unregistered,
        Active,
        Inactive,
        Banned
    }

    struct Agent {
        address developer;
        string name;
        string metadataURI;
        string[] capabilities;
        uint256 reputation;
        Status status;
        uint256 createdAt;
        uint256 updatedAt;
    }

    mapping(address => Agent) private agents;
    address[] private agentIndex;
    mapping(address => bool) private isIndexed;

    address public reputationOracle;

    event AgentRegistered(address indexed agent, address indexed developer, string name, string metadataURI);
    event AgentUpdated(address indexed agent, Status status);
    event ReputationOracleUpdated(address indexed oracle);
    event ReputationSynced(address indexed wallet, uint256 reputation);

    modifier onlyReputationOracle() {
        require(msg.sender == reputationOracle, "AgentRegistry: not reputation oracle");
        _;
    }

    constructor(address initialOwner) Ownable(initialOwner) {
        reputationOracle = initialOwner;
    }

    function registerAgent(
        address agentAddress,
        string calldata name,
        string calldata metadataURI,
        string[] calldata capabilities
    ) external {
        Agent storage profile = agents[agentAddress];
        require(profile.status == Status.Unregistered, "AgentRegistry: already registered");

        profile.developer = msg.sender;
        profile.name = name;
        profile.metadataURI = metadataURI;
        _setCapabilities(profile, capabilities);
        profile.status = Status.Active;
        profile.createdAt = block.timestamp;
        profile.updatedAt = block.timestamp;

        if (!isIndexed[agentAddress]) {
            agentIndex.push(agentAddress);
            isIndexed[agentAddress] = true;
        }

        emit AgentRegistered(agentAddress, msg.sender, name, metadataURI);
    }

    function updateAgent(
        address agentAddress,
        string calldata name,
        string calldata metadataURI,
        string[] calldata capabilities,
        Status status
    ) external {
        Agent storage profile = agents[agentAddress];
        require(profile.status != Status.Unregistered, "AgentRegistry: not registered");
        require(profile.developer == msg.sender, "AgentRegistry: not developer");
        require(status != Status.Unregistered, "AgentRegistry: invalid status");

        profile.name = name;
        profile.metadataURI = metadataURI;
        _setCapabilities(profile, capabilities);
        profile.status = status;
        profile.updatedAt = block.timestamp;

        emit AgentUpdated(agentAddress, status);
    }

    function adminUpdateStatus(address agent, Status status) external onlyOwner {
        Agent storage profile = agents[agent];
        require(profile.status != Status.Unregistered, "AgentRegistry: not registered");
        profile.status = status;
        profile.updatedAt = block.timestamp;
        emit AgentUpdated(agent, status);
    }

    function setReputationOracle(address oracle) external onlyOwner {
        reputationOracle = oracle;
        emit ReputationOracleUpdated(oracle);
    }

    function syncReputation(address agent, uint256 reputation) external onlyReputationOracle {
        Agent storage profile = agents[agent];
        require(profile.status != Status.Unregistered, "AgentRegistry: not registered");
        profile.reputation = reputation;
        profile.updatedAt = block.timestamp;
        emit ReputationSynced(agent, reputation);
    }

    function getAgent(address wallet) external view returns (Agent memory) {
        return agents[wallet];
    }

    function getAgents(uint256 offset, uint256 limit) external view returns (Agent[] memory list, uint256 total) {
        total = agentIndex.length;
        if (offset >= total) {
            return (new Agent[](0), total);
        }

        uint256 end = offset + limit;
        if (end > total) {
            end = total;
        }

        list = new Agent[](end - offset);
        for (uint256 i = offset; i < end; i++) {
            list[i - offset] = agents[agentIndex[i]];
        }
    }

    function getAllAgents() external view returns (Agent[] memory list) {
        list = new Agent[](agentIndex.length);
        for (uint256 i = 0; i < agentIndex.length; i++) {
            list[i] = agents[agentIndex[i]];
        }
    }

    function isAgentActive(address wallet) external view returns (bool) {
        return agents[wallet].status == Status.Active;
    }

    function getDeveloper(address agent) external view returns (address) {
        return agents[agent].developer;
    }

    function agentCount() external view returns (uint256) {
        return agentIndex.length;
    }

    function _setCapabilities(Agent storage profile, string[] calldata capabilities) internal {
        delete profile.capabilities;
        for (uint256 i = 0; i < capabilities.length; i++) {
            profile.capabilities.push(capabilities[i]);
        }
    }
}
