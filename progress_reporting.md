# Project Meetings and Progress Log

This document summarizes the major project meetings, development milestones, and collaborative decisions made throughout the implementation of Assignments 2 and 3. The project was developed collaboratively, with all members participating in design discussions, implementation, debugging, testing, and writing code together during the majority of development sessions.

---

# 12 May 2025 – Assignment 2 Implementation

**Attendees:** All group members

## Topics discussed

- Reviewed the requirements and protocol specification for Assignment 2.
- Designed the communication protocol between the three clients and the server.
- Discussed how to coordinate the signing process across multiple participants.
- Planned the synchronization mechanism required before beginning the protocol.

## Work completed

- Implemented peer discovery and identification using public keys.
- Added readiness synchronization between all participating clients.
- Implemented challenge handling and nonce distribution.
- Implemented local signing and signature exchange between peers.
- Added bundle collection and submission to the server.
- Implemented turn-passing logic to ensure responsibility for requesting challenges rotates correctly between participants.
- Performed initial end-to-end testing and verified successful execution of the protocol.

---

# 27 May 2025 – Initial Assignment 3 Implementation

**Attendees:** All group members

## Topics discussed

- Designed the blockchain data structures and networking protocol.
- Planned transaction propagation, mining, synchronization, and validation between nodes.
- Discussed blockchain persistence and communication with the testing server.

## Work completed

- Implemented the `Block` and `Transaction` data structures.
- Implemented transaction hashing, block hashing, and proof-of-work verification.
- Added mining functionality and block propagation between peers.
- Implemented mempool management and transaction validation.
- Implemented blockchain registration with the course server.
- Established communication with the testing infrastructure and successfully registered the blockchain.
- At this stage, the blockchain executed correctly but only received a single response from the server and did not yet satisfy all confirmation requirements.

---

# 8 June 2025 – Debugging and Functional Validation

**Attendees:** All group members

## Topics discussed

- Investigated why the blockchain was not passing server validation.
- Reviewed synchronization logic, transaction handling, and mining behaviour.
- Performed extensive debugging and validation against the assignment specification.

## Work completed

- Identified and fixed the issues preventing successful confirmation by the server.
- Corrected blockchain synchronization behaviour and transaction processing.
- Improved handling of mined blocks and mempool updates.
- Re-tested the implementation across multiple runs.
- Achieved a fully functional baseline implementation satisfying the assignment requirements.

---

# 13 June 2025 – Final Polishing and Extensions

**Attendees:** All group members

## Topics discussed

- Reviewed overall code quality and documentation.
- Discussed additional testing strategies and possible extensions beyond the assignment requirements.
- Evaluated approaches for improving blockchain synchronization performance.

## Work completed

- Expanded the automated test suite with additional unit tests.
- Improved project documentation and usage instructions.
- Refactored portions of the implementation for clarity and maintainability.
- Implemented an extension inspired by the bonus assignment on fork convergence after network partitions, introducing efficient fork detection using binary-search-based divergence discovery and selective synchronization of only the differing chain suffix.
- Performed final integration testing and repository cleanup in preparation for submission.

---

# Development Process

Development was carried out in a collaborative manner. Rather than splitting the project into isolated tasks, the group worked together during most implementation sessions, jointly discussing designs, writing code, debugging issues, and validating functionality.

The majority of the codebase was written collaboratively, with group members actively programming together instead of working on separate isolated components. Design decisions were discussed collectively before implementation, and debugging sessions were performed jointly.

Meetings were complemented by day-to-day communication through group messaging, where minor fixes and debugging updates were discussed as they arose.
