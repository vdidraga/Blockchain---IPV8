import struct, time
from hashlib import sha256
from dataclasses import dataclass
from hashlib import sha256
from ipv8.keyvault.crypto import default_eccrypto

@dataclass
class Block:
    height: int
    prev_hash: bytes
    txs_hash: bytes
    timestamp: int
    difficulty: int
    nonce: int
    block_hash: bytes
    tx_hashes: list[bytes]

@dataclass
class Transaction:
    sender_key: bytes
    data: bytes
    timestamp: int
    signature: bytes

# TODO: Change this
genesis_block = Block(
    height=0,
    prev_hash=bytes(32),
    txs_hash=sha256(b"").digest(),
    timestamp=0,
    difficulty=0,
    nonce=0,
    block_hash=bytes(32),
    tx_hashes=[]
)

# headers n stuff
def pack_block_header(prev_hash: bytes, txs_hash: bytes, timestamp: int, difficulty: int, nonce: int) -> bytes:
    assert len(prev_hash) == 32, "stoopid"
    assert len(txs_hash) == 32,  "dumbass"
    return(prev_hash + txs_hash + struct.pack(">Q", timestamp) + struct.pack(">I", difficulty) + struct.pack(">Q", nonce))

def block_to_header(block: Block) -> bytes:
    return pack_block_header(block.prev_hash, block.txs_hash, block.timestamp, block.difficulty, block.nonce)

def compute_block_hash(header: bytes) -> bytes:
    return sha256(header).digest()

def check_pow(block_hash: bytes, difficulty: int) -> bool:
    return int.from_bytes(block_hash, "big") >> (256 - difficulty) == 0

def compute_txs_hash(tx_hashes: list[bytes]) -> bytes:
    payload = b"".join(tx_hashes)
    return sha256(payload).digest()

# transactions n stuff
def verify_transaction_signature(tx: Transaction) ->  bool:
    timestamp_8byte_be = struct.pack(">Q", tx.timestamp)
    assert len(timestamp_8byte_be) == 8, "Verify Timestamp is not 8 bytes"

    message = tx.sender_key + tx.data + timestamp_8byte_be
    public_key = default_eccrypto.key_from_public_bin(tx.sender_key)
    
    return default_eccrypto.is_valid_signature(public_key, message, tx.signature)

def compute_transaction_hash(tx: Transaction) -> bytes:
    return sha256(tx.sender_key + tx.data + struct.pack(">Q", tx.timestamp) + tx.signature).digest()

# minin' n stuff
def pow_search(block: Block) -> Block:
    while block.nonce < 10_100_000_000:
        if block.nonce % 10_000_000 == 0:
            print(f'Looked through {block.nonce:,} nonces')

        header = block_to_header(block)
        hash = compute_block_hash(header)
        if check_pow(hash, block.difficulty):
            print(f"Found block! {block}")
            block.block_hash = hash
            return block
        block.nonce += 1
    raise Exception(f"Nonce not found for block {block}")

def mine_block(height: int, prev_hash: bytes, transactions: list[Transaction], difficulty: int) -> Block:
    tx_hashes = [compute_transaction_hash(tx) for tx in transactions]
    txs_hash = compute_txs_hash(tx_hashes)
    timestamp = int(time.time())

    possible = Block(height, prev_hash, txs_hash, timestamp, difficulty, 0, bytes(32), tx_hashes)
    print("Mining summ blocks")
    return pow_search(possible)

def mine_block_with_stop(
        height: int, 
        prev_hash: bytes,
        transactions: list[Transaction],
        difficulty: int,
        job_id: int,
        should_stop
) -> Block | None:
    tx_hashes = [compute_transaction_hash(tx) for tx in transactions]
    txs_hash = compute_txs_hash(tx_hashes)
    timestamp = int(time.time())

    possible = Block(height, prev_hash, txs_hash, timestamp, difficulty, 0, bytes(32), tx_hashes)
    print("Mining summ stopping blocks")

    while possible.nonce < 10_100_000_000:
        if should_stop():
            return None
        if possible.nonce % 10_000_000 == 0:
            print(f"Looked through {possible.nonce:,} nonces")

        header = block_to_header(possible)
        block_hash = compute_block_hash(header)

        if check_pow(block_hash, possible.difficulty):
            print(f"Found sblock!: {possible}")
            possible.block_hash = block_hash
            return possible

        possible.nonce += 1

def verify_block(block: Block) -> bool:
    header = block_to_header(block)
    hash = compute_block_hash(header)
    
    if hash != block.block_hash:
        return False
    
    elif not check_pow(hash, block.difficulty):
        return False
    
    elif compute_txs_hash(block.tx_hashes) != block.txs_hash:
        return False
    
    else:
        return True

def verify_prev_links_cleanly(block: Block, tipHash: bytes) -> bool:
    
    if block.prev_hash != tipHash:
        return False
    
    return True

genesis_block.block_hash = compute_block_hash(block_to_header(genesis_block))