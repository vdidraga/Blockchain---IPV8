import struct, time
from hashlib import sha256
from dataclasses import dataclass
from hashlib import sha256
from ipv8.keyvault.crypto import default_eccrypto
import os

from client3_miner import *

DIFFICULTY = 10

# GENESIS
def test_genesis_block_valid():
    assert verify_block(genesis_block)
    assert genesis_block.height == 0
    assert genesis_block.prev_hash == bytes(32)

def test_genesis_is_deterministic():
    header = pack_block_header(bytes(32), sha256(b"").digest(), 0, 0, 0)
    expected_hash = compute_block_hash(header)
    assert genesis_block.block_hash == expected_hash


# HEADERS
def test_pack_header_length():
    header = pack_block_header(bytes(32), bytes(32), 0, 0, 0)
    assert len(header) == 84

def test_block_hash_deterministic():
    header = pack_block_header(bytes(32), bytes(32), 123, 20, 42)
    assert compute_block_hash(header) == compute_block_hash(header)

def test_block_hash_changes_with_nonce():
    h1 = pack_block_header(bytes(32), bytes(32), 0, 0, 1)
    h2 = pack_block_header(bytes(32), bytes(32), 0, 0, 2)

    assert compute_block_hash(h1) != compute_block_hash(h2)


# POW CHECKING
# any pass at diff 0
def test_pow_check_zero_difficulty():
    assert check_pow(bytes(32), 0)
    assert check_pow(b"\xff" * 32, 0)

# check 8 leading against 8 needed and 9 needed
def test_pow_check_respects_leading_zeros():
    h = bytes([0]) + b"\xff" * 31
    assert check_pow(h, 8)
    assert not check_pow(h, 9)

def test_mine_block_valid_pow():
    block = mine_block_with_stop(height = 1, prev_hash = genesis_block.block_hash, transactions = [], job_id = 0, difficulty = DIFFICULTY, should_stop = lambda: False)
    assert block is not None
    assert verify_block(block)
    assert verify_prev_links_cleanly(block, genesis_block.block_hash)


# HASHES
def test_txs_hash_empty():
    assert compute_txs_hash([]) == sha256(b"").digest()

def test_tx_hash_deterministic():
    tx1 = Transaction(bytes(32), b"data", 1234, bytes(64))
    tx2 = Transaction(bytes(32), b"data", 1234, bytes(64))
    assert compute_transaction_hash(tx1) == compute_transaction_hash(tx2)

def test_txs_hash_ordering():
    t1 = compute_transaction_hash(Transaction(bytes(32), b"1", 1234, bytes(64)))
    t2 = compute_transaction_hash(Transaction(bytes(32), b"2", 1234, bytes(64)))
    assert compute_txs_hash([t1,t2]) != compute_txs_hash([t2,t1])

def test_tx_hash_changes_when_data_changes():
    tx1 = Transaction(bytes(32), b"a", 1, bytes(64))
    tx2 = Transaction(bytes(32), b"b", 1, bytes(64))

    assert compute_transaction_hash(tx1) != compute_transaction_hash(tx2)

# BLOCK VALIDATION
def test_verify_rejects_wrong_block_hash():
    block = mine_block_with_stop(height = 1, prev_hash = genesis_block.block_hash, transactions = [], job_id = 0, difficulty = DIFFICULTY, should_stop = lambda: False)
    assert block is not None
    block.block_hash = bytes(32)
    assert not verify_block(block)

def test_verify_rejects_wrong_txs_hash():
    block = mine_block_with_stop(height = 1, prev_hash = genesis_block.block_hash, transactions = [], job_id = 0, difficulty = DIFFICULTY, should_stop = lambda: False)
    assert block is not None
    block.txs_hash = bytes(32)
    assert not verify_block(block)

def test_verify_prev_links_rejects_wrong_prev():
    block = mine_block_with_stop(height = 1, prev_hash = genesis_block.block_hash, transactions = [], job_id = 0, difficulty = DIFFICULTY, should_stop = lambda: False)
    assert block is not None
    assert not verify_prev_links_cleanly(block, bytes(32))

def test_mine_block_ret_none_on_stop():
    block = mine_block_with_stop(height = 1, prev_hash = genesis_block.block_hash, transactions = [], job_id = 0, difficulty = DIFFICULTY, should_stop = lambda: True)
    assert block is None

def test_mine_block_properly():
    key = default_eccrypto.generate_key("curve25519")
    pub = key.pub().key_to_bin()
    timestamp = 1234
    data = b"George Bush doesn't care about black people."
    message = pub + data + struct.pack(">Q", timestamp)
    sig = default_eccrypto.create_signature(key, message)
    tx = Transaction(pub, data, timestamp, sig)
    
    block = mine_block_with_stop(height = 1, prev_hash = genesis_block.block_hash, transactions = [tx], job_id = 0, difficulty = DIFFICULTY, should_stop = lambda: False)
    assert block is not None
    assert verify_block(block)
    assert block.txs_hash == compute_txs_hash([compute_transaction_hash(tx)])
    assert len(block.tx_hashes) == 1

def test_mine_block_multiple_transactions():
    key1 = default_eccrypto.generate_key("curve25519")
    pub1 = key1.pub().key_to_bin()

    timestamp1 = 1234
    data1 = b"first transaction"
    message1 = pub1 + data1 + struct.pack(">Q", timestamp1)
    sig1 = default_eccrypto.create_signature(key1, message1)

    tx1 = Transaction(pub1, data1, timestamp1, sig1)

    key2 = default_eccrypto.generate_key("curve25519")
    pub2 = key2.pub().key_to_bin()

    timestamp2 = 5678
    data2 = b"second transaction"
    message2 = pub2 + data2 + struct.pack(">Q", timestamp2)
    sig2 = default_eccrypto.create_signature(key2, message2)

    tx2 = Transaction(pub2, data2, timestamp2, sig2)

    block = mine_block_with_stop(
        height=1,
        prev_hash=genesis_block.block_hash,
        transactions=[tx1, tx2],
        difficulty=DIFFICULTY,
        job_id=0,
        should_stop=lambda: False,
    )

    assert block is not None
    assert verify_block(block)
    assert len(block.tx_hashes) == 2

    expected_hashes = [
        compute_transaction_hash(tx1),
        compute_transaction_hash(tx2),
    ]

    assert block.tx_hashes == expected_hashes
    assert block.txs_hash == compute_txs_hash(expected_hashes)

# SIGNATURE VALIDATION
def test_signature_verification():
    key = default_eccrypto.generate_key("curve25519")
    pub = key.pub().key_to_bin()

    timestamp = 1234
    data = b"i am good"
    message = pub + data + struct.pack(">Q", timestamp)
    sig = default_eccrypto.create_signature(key, message)

    tx = Transaction(pub, data, timestamp, sig)
    assert verify_transaction_signature(tx)

def test_signature_verification_refuses_tampered():
    key = default_eccrypto.generate_key("curve25519")
    pub = key.pub().key_to_bin()

    timestamp = 1234
    data = b"i am good"
    message = pub + data + struct.pack(">Q", timestamp)
    sig = default_eccrypto.create_signature(key, message)

    evil_data = b"i am eeeevil"
    tx = Transaction(pub, evil_data, timestamp, sig)
    assert not verify_transaction_signature(tx)