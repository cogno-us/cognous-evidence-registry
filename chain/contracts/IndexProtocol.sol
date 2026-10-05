// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

/// @notice Local reference protocol. Inclusion is not truth or BitRep verification.
/// No owner, proxy, delegatecall, upgrade, token, or administrative admission path.
contract IndexProtocol {
    bytes32 public constant POLICY = sha256("index-lifecycle/1");
    bytes32 public immutable DOMAIN;
    enum Lifecycle { Absent, Active, Withdrawn, Superseded }
    struct Claim {
        address author;
        bytes32 content;
        bytes32 parent;
        Lifecycle lifecycle;
        bytes32 successor;
    }
    struct Evidence {
        address submitter;
        bytes32 claim;
        bytes32 content;
        bytes32 manifest;
        bytes32 statement;
        uint8 relation; // 1: support assertion; 2: contradiction/challenge assertion
    }
    mapping(bytes32 => Claim) public claims;
    mapping(bytes32 => Evidence) public evidence;
    event Registered(bytes32 indexed id, address indexed author, bytes32 content, bytes32 parent);
    event EvidenceSubmitted(bytes32 indexed id, bytes32 indexed claim, address indexed submitter,
        bytes32 content, bytes32 manifest, bytes32 statement, uint8 relation);
    event LifecycleChanged(bytes32 indexed id, Lifecycle lifecycle, bytes32 successor, bytes32 reason);

    constructor() {
        DOMAIN = keccak256(abi.encode("index-domain/1", block.chainid, address(this), POLICY));
    }
    modifier domain(bytes32 expected) {
        require(expected == DOMAIN, "wrong domain");
        _;
    }
    function claimId(address author, bytes32 content, bytes32 parent) public view returns (bytes32) {
        return keccak256(abi.encode(DOMAIN, "claim", author, content, parent));
    }
    function register(bytes32 expected, bytes32 content, bytes32 parent) external domain(expected)
        returns (bytes32 id) {
        require(content != bytes32(0), "empty commitment");
        require(parent == bytes32(0) || claims[parent].author != address(0), "missing parent");
        id = claimId(msg.sender, content, parent);
        require(claims[id].author == address(0), "duplicate claim");
        claims[id] = Claim(msg.sender, content, parent, Lifecycle.Active, bytes32(0));
        emit Registered(id, msg.sender, content, parent);
    }
    function submitEvidence(bytes32 expected, bytes32 claim, bytes32 content, bytes32 manifest,
        bytes32 statement, uint8 relation) external domain(expected) returns (bytes32 id) {
        require(claims[claim].author != address(0), "missing claim");
        require(content != bytes32(0) && manifest != bytes32(0), "empty commitment");
        require(relation == 1 || relation == 2, "invalid relation");
        id = keccak256(abi.encode(DOMAIN, "evidence", msg.sender, claim, content, manifest, statement, relation));
        require(evidence[id].submitter == address(0), "duplicate evidence");
        evidence[id] = Evidence(msg.sender, claim, content, manifest, statement, relation);
        emit EvidenceSubmitted(id, claim, msg.sender, content, manifest, statement, relation);
    }
    function withdraw(bytes32 expected, bytes32 id, bytes32 reason) external domain(expected) {
        Claim storage c = claims[id];
        require(c.author == msg.sender, "not author");
        require(c.lifecycle == Lifecycle.Active, "terminal lifecycle");
        require(reason != bytes32(0), "empty reason");
        c.lifecycle = Lifecycle.Withdrawn;
        emit LifecycleChanged(id, c.lifecycle, bytes32(0), reason);
    }
    function supersede(bytes32 expected, bytes32 id, bytes32 successor, bytes32 reason)
        external domain(expected) {
        Claim storage c = claims[id];
        Claim storage next = claims[successor];
        require(c.author == msg.sender && next.author == msg.sender, "not author");
        require(c.lifecycle == Lifecycle.Active && next.lifecycle == Lifecycle.Active, "terminal lifecycle");
        require(next.parent == id && successor != id, "invalid successor");
        require(reason != bytes32(0), "empty reason");
        c.lifecycle = Lifecycle.Superseded;
        c.successor = successor;
        emit LifecycleChanged(id, c.lifecycle, successor, reason);
    }
}
