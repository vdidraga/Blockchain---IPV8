# Blockchain Engineering Assignments Repository

This was a very fun set of assignments!

### Authors:
- Jacek Kulik
- Antreas Ioannou
- Victor Didraga
Contact email: v.a.didraga@student.tudelft.nl

### How to run

1. Set up a virutal environment using your preferred Python package manager, recommended Python version: 3.13
2. Install the Python requirements, for example 
```bash
pip install -r requirements.txt
```
3. Set up a `.env` file according to the instructions provided in `.env.example`
4. Run one of the client programs, for example:
```bash
python client_3_blockchain.py
```

### How to test

1. Set up according to [How to run](#how-to-run)
2. Run 
```bash
pytest tests/ -v
```
To run all the tests or
```bash
pytest tests/[test_name].py -v
```
To run a specific test

## Explanations of Files

### client_1.py

Client for the 1st assignment. Uses `mine.py` to find a nonce and then continuously resends it until it receives a response from the server.

### nonce_finder.py

Miner for 1st assignment. Compiles a payload and mines a nonce for it.

### client_2.py

Client for the 2nd assignment. If 1st, starts be requesting the challenge. Upon solving it sends it back and passes turn to the next peer. Then the cycle continues until its done.

### client_3_blockchain.py

Main client file for Assignment 3. Connects to other peers on the community and stars mining blocks. Accepts transactions from peers on the community. Upon finding a block communicates it to other miners. Upon receiving a block, investigates it and appends it, ignores it, or attempts to sync to a different chain.

### client_3_registration.py

Client for the Assignment 3 submission server. Sends a request to join our community.

### client3_miner.py

Mining file for Assignment 3. Deals with storing blocks, computing their hashes, and mining them.

### test_miner.py

Test file for the `client3_miner.py`