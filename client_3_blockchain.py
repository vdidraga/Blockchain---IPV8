import asyncio
from dataclasses import dataclass
import signal
from ipv8.community import Community, CommunitySettings
from ipv8.configuration import ConfigBuilder, WalkerDefinition, Strategy, default_bootstrap_defs
from ipv8.util import run_forever
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import PeerObserver
from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.lazy_community import lazy_wrapper
from ipv8_service import IPv8
from dotenv import load_dotenv
from os import getenv
import json

from client3_miner import Transaction, Block, genesis_block, mine_block_with_stop, compute_transaction_hash, compute_block_hash, block_to_header, verify_block, verify_prev_links_cleanly, verify_transaction_signature
from typing import List
import threading

load_dotenv()

PARTITION=False
LOAD_FROM_FILE=True

# Load environment variables 
community_3_id = getenv("CLIENT_3_COMMUNITY_ID", "")
GROUP_ID = getenv("GROUP_ID", "")
MY_ORDER = int(getenv("MY_ORDER", -1))
KEYS_FILE = getenv("KEYS_FILE", "")
assert "" not in [community_3_id, GROUP_ID, KEYS_FILE]
assert MY_ORDER != -1
COMMUNITY_ID = bytes.fromhex(community_3_id)

SERVER_PUBLIC_KEY = bytes.fromhex(
    "4c69624e61434c504b3ae3fc099fb56ca3b5e1de9a1c843387f2acdbb78b1bd4350ffde518068a0d246344b10d0d8c355fd0d76873e7d7f7838f3715e025af08f791324495e083331ce6"
)

PUBLIC_KEY_1 = bytes.fromhex(
    "4c69624e61434c504b3a6ddc887fd7a98d41126d24eb4d3349f27683c555698c94b80b0a11bb43c2f6765645e827f4c331c3eb653f1f52d38683423e6b013c25f3157ed8adbf86aa997a"
)
PUBLIC_KEY_2 = bytes.fromhex(
    "4c69624e61434c504b3ae9a6f3ee192bcb9833fe647728a19e74d6b7fe2e42efe96f4de40d4922aa7a3dcb7c47a5f1776db9902548aab9fb4ef06dd1dc39b12f99f5e8326334ebe7fcd3"
)
PUBLIC_KEY_3 = bytes.fromhex(
    "4c69624e61434c504b3a87ca1dee80e128d6ad389fb7b2fd1f99bfa86377fdf3815e97b734d767c48840dc818b5467b27b8fad1e434e07005e05eac40a726334a5b3a83b289a51ca097c"
)

# List of keys of other miners
PUBLIC_KEYS = [PUBLIC_KEY_1, PUBLIC_KEY_2, PUBLIC_KEY_3]

# List of clients from whom we accept transactions
CLIENT_KEYS = [SERVER_PUBLIC_KEY]
DIFFICULTY = 20
MAX_DISAGREEMENT_DEPTH = 50000

ALL_PEER_KEYS = {
    PUBLIC_KEY_1: 0,
    PUBLIC_KEY_2: 1,
    PUBLIC_KEY_3: 2,
}

OTHER_PEER_KEYS = {
    key: idx for key, idx in ALL_PEER_KEYS.items()
    if key != PUBLIC_KEYS[MY_ORDER - 1]
}

@dataclass
class SubmitTransactionMessage(DataClassPayload[1]):
    sender_key: bytes
    data: bytes
    timestamp: int
    signature: bytes

@dataclass
class SubmitTransactionResponseMessage(DataClassPayload[2]):
    success: bool
    tx_hash: bytes
    message: str

@dataclass
class BlockBroadcastMessage(DataClassPayload[9]):
    height: int
    prev_hash: bytes
    txs_hash: bytes
    timestamp: int
    difficulty: int
    nonce: int
    block_hash: bytes
    tx_hashes: bytes

@dataclass
class GetChainHeight(DataClassPayload[3]):
    request_id: int


@dataclass
class ChainHeightResponse(DataClassPayload[4]):
    request_id: int
    height: int
    tip_hash: bytes

@dataclass
class GetBlock(DataClassPayload[5]):
    height: int

@dataclass
class BlockResponse(DataClassPayload[6]):
    height: int
    prev_hash: bytes
    txs_hash: bytes
    timestamp: int
    difficulty: int
    nonce: int
    block_hash: bytes
    tx_hashes: bytes
@dataclass
class HashRequest(DataClassPayload[7]):
    height: int

@dataclass
class HashResponse(DataClassPayload[8]):
    height: int
    hash: bytes

@dataclass
class DoubleHashRequest(DataClassPayload[10]):
    height: int

@dataclass
class DoubleHashResponse(DataClassPayload[11]):
    height: int
    hash: bytes
    hash_previous: bytes

# Trigger dataclass payload compilation.
_ = SubmitTransactionMessage(bytes(0), bytes(0), 0, bytes(0))
_ = SubmitTransactionResponseMessage(False, bytes(0), "")
_ = GetChainHeight(0)
_ = ChainHeightResponse(0, 0, bytes(0))
_ = GetBlock(0)
_ = BlockResponse(0, bytes(0), bytes(0), 0, 0, 0, bytes(0), bytes(0))
_ = HashRequest(0)
_ = HashResponse(0, bytes(0))
_ = BlockBroadcastMessage(0, bytes(0), bytes(0), 0, 0, 0, bytes(0), bytes(0))
_ = DoubleHashRequest(0)
_ = DoubleHashResponse(0, bytes(0), bytes(0))

class BlockchainEngineeringCommunity(Community, PeerObserver):
    community_id = COMMUNITY_ID

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)

        self.add_message_handler(SubmitTransactionMessage, self.on_submit_transaction)
        self.add_message_handler(GetChainHeight, self.on_get_chain_height)
        self.add_message_handler(GetBlock, self.on_get_block)
        self.add_message_handler(BlockResponse, self.on_block_response)
        self.add_message_handler(BlockBroadcastMessage, self.on_block_broadcast)
        self.add_message_handler(HashRequest, self.on_hash_request)
        self.add_message_handler(HashResponse, self.on_hash_response)
        self.add_message_handler(DoubleHashRequest, self.on_double_hash_request)
        self.add_message_handler(DoubleHashResponse, self.on_double_hash_response)

        self.server = None
        self.peers: dict[bytes, Peer | None] = {}
        self.mempool: List[Transaction] = []
        self.mempool_storage: dict[bytes, Transaction] = {}
        self.task: None | asyncio.Task = None

        self.chain: list[Block] = [genesis_block]
        self.pending_blocks: list[Block] = []   

        self.sync_their_height: int = 0
        self.sync_peer: Peer | None = None
        self.sync_block_count: int = 0
        self.sync_block_buffer: list[Block] = []
        self.fork_height: int = 0

        self.mining_job_id = 0  
        self.mining_stop_event = threading.Event()
        self.mining_thread: threading.Thread | None = None

        self.ignored_peers: set[bytes] = set()

        self.search_low: int = 0
        self.search_high: int = 0
        self.peer0: Peer | None = None

    def started(self) -> None:
        print("Started peer")
        print("I am public key:", self.my_peer.public_key.key_to_bin().hex())

        if LOAD_FROM_FILE:
            self.load_chain_from_file()

        self.network.add_peer_observer(self)
        self.start_pow_search_task()
        # Store myself.

    def on_peer_added(self, peer: Peer) -> None:
        peer_key = peer.public_key.key_to_bin()
        peer_address = peer.address

        print(f"I found: {peer_key.hex()} at {peer_address}")

        if peer_key == SERVER_PUBLIC_KEY:
            print("Found server!")
            self.server = peer

        elif peer_key in OTHER_PEER_KEYS:
            self.peers[peer_key] = peer
            print(f"Found peer {OTHER_PEER_KEYS[peer_key] + 1}")
            
        
        if peer_key == PUBLIC_KEY_1:
            self.peer0 = peer
        
        print(f"Current peers state: {[p.address if p else None for p in self.peers.values()]}")
        print(f"Server: {self.server.address if self.server else None}")

    def on_peer_removed(self, peer: Peer) -> None:
        key = peer.public_key.key_to_bin()
        if key == SERVER_PUBLIC_KEY:
            self.server = None
        self.peers.pop(key, None)

    def send_to_others(self, payload: DataClassPayload) -> None:
        for peer in self.peers.values():
            if peer is None:
                continue
            self.ez_send(peer, payload)
    
    def load_chain_from_file(self) -> None:
        "Loads the blockchain from the chain.json file"
        print("Loading the blockchain...")

        try:
            with open("chain.json", "r") as file:
                content = file.read()
                chain = json.loads(content)
                chain_converted = [Block.from_json(block) for block in chain]
                self.chain = chain_converted

            print(f"Successfully loaded chain of height: {len(self.chain)-1}")
        except Exception as e:
            print(f"Failed to load chain: {e}")
    
    def start_pow_search_task(self)  -> None:
        """
        This function (re)starts a PoW search task
        It is called any time a transaction has been added to the mempool.
        """
        print("Starting mining")

        self.mining_job_id += 1
        current_job_id = self.mining_job_id

        self.mining_stop_event.set()

        if self.mining_thread is not None and self.mining_thread.is_alive():
            # Avoid deadlock/runtime error if restart is triggered by the worker itself.
            if self.mining_thread is not threading.current_thread():
                self.mining_thread.join(timeout=0)

        self.mining_stop_event = threading.Event()
        self.mining_thread = threading.Thread(
            target=self.pow_worker,
            args=(current_job_id, self.mining_stop_event),
            daemon=True
        )
        self.mining_thread.start()

    def pow_worker(self, job_id: int, stop_event: threading.Event) -> None:
        if not self.mempool:
            print("Empty mempool")
            # return
        
        block = mine_block_with_stop(
            len(self.chain),
            self.chain[-1].block_hash,
            self.mempool,
            DIFFICULTY,
            job_id,
            lambda: stop_event.is_set() or job_id != self.mining_job_id
        )

        if block is None:
            # print("None block!?!?")
            return
        if job_id != self.mining_job_id or stop_event.is_set():
            print("Stale block mined")
            return
        self.on_block_found(block)
        

    def on_block_found(self, block: Block) -> None:
        print("Found block function called")

        self.chain.append(block)

        included_hashes = set(block.tx_hashes)

        self.mempool = [
            tx for tx in self.mempool 
            if compute_transaction_hash(tx) not in included_hashes
        ]
        
        print(f"Chain height is now {block.height}")
        
        message = BlockBroadcastMessage(
            block.height,
            block.prev_hash,
            block.txs_hash,
            block.timestamp,
            block.difficulty,
            block.nonce,
            block.block_hash,
            b"".join(block.tx_hashes),
        )

        if PARTITION:
            if message.height <= 60 and MY_ORDER != 1:
                self.peers[PUBLIC_KEY_1] = None
                self.send_to_others(message)
            if message.height <= 60 and MY_ORDER == 1:
                pass
            if message.height > 60 and MY_ORDER != 1:
                assert self.peer0 is not None
                self.peers[PUBLIC_KEY_1] = self.peer0
                self.send_to_others(message)
            if message.height > 60 and MY_ORDER == 1:
                self.send_to_others(message)
        else:
            self.send_to_others(message)
            
        print("finished mining")
        self.start_pow_search_task()
    
    def save_chain(self) -> None:
        print("Saving the chain...")
        data = json.dumps([block.to_json() for block in self.chain])
        with open("chain.json", "w") as file:
            try:
                file.write(data)
            except Exception as e:
                print(f"Error during saving chain: {e}")
    
    def compute_mid(self) -> int:
        """Computes the middle point for the binary search of Divergence Point"""
        return self.search_low + (self.search_high - self.search_low) // 2

    @lazy_wrapper(BlockBroadcastMessage)
    def on_block_broadcast(self, peer: Peer, payload: BlockBroadcastMessage) -> None:
        if peer.public_key.key_to_bin() not in PUBLIC_KEYS or peer.public_key.key_to_bin() in self.ignored_peers:
            #print("Received block broadcast from unknown peer")
            return

        block = Block(
            payload.height,
            payload.prev_hash,
            payload.txs_hash,
            payload.timestamp,
            payload.difficulty,
            payload.nonce,
            payload.block_hash,
            [payload.tx_hashes[i:i+32] for i in range(0, len(payload.tx_hashes), 32)]
        )

        block.block_hash = compute_block_hash(block_to_header(block))

        if not verify_block(block):
            print(f"Received invalid block: {block}")
            return
        
        if not verify_prev_links_cleanly(block, self.chain[-1].block_hash):
            print("Received unlinked block")
            print(
                f"Link mismatch: block.height={block.height}, "
                f"block.prev_hash={block.prev_hash.hex()}, "
                f"local_tip_height={self.chain[-1].height}, "
                f"local_tip_hash={self.chain[-1].block_hash.hex()}"
            )

            if block.height < len(self.chain)-1:
                print("Received unlinked block is behind, ignoring")
                return
            
            elif block.height == len(self.chain)-1:
                print("Received unlinked block is at the same level as ours, ignoring")
                return

            if block.height == 1:
                print("Genesis block is not linked to suggest block at height 1")
                return None
            
            elif block.height > len(self.chain)-1:
                print("Received unlinked block is ahead of ours, adopting")

                # Set up things for sync and disagreement search
                self.sync_peer = peer
                self.sync_their_height = block.height
                self.search_low = max(0, len(self.chain)-MAX_DISAGREEMENT_DEPTH)
                self.search_high = len(self.chain) - 1
                # First check if we disagree to deep
                if len(self.chain) > MAX_DISAGREEMENT_DEPTH:
                    self.ez_send(peer, HashRequest(len(self.chain) - MAX_DISAGREEMENT_DEPTH))
                else:
                    self.ez_send(peer, DoubleHashRequest(self.compute_mid()))
                return
        
        if block.height < len(self.chain)-1:
            print("Received linked block is behind, ignoring,  wtf")
        
        elif block.height == len(self.chain)-1:
            print("Received linked block is at the same level as ours, ignoring, wtf")
        
        elif block.height == len(self.chain):
            print("Received linked block is ahead of ours, appending")

            # First clean mempool of transactions in the block
            included_hashes = set(block.tx_hashes)
            self.mempool = [
                tx for tx in self.mempool 
                if compute_transaction_hash(tx) not in included_hashes
            ]
            self.chain.append(block)

            # Then restart pow search
            self.start_pow_search_task()
        elif block.height > len(self.chain):
            print("Received LINKED block is more than 1 ahead of ours, what just happened")
  
    def sync_their_tip(self, peer: Peer, fork_height: int, tip_height: int) -> None:
        for h in range(fork_height, tip_height + 1):
            self.ez_send(peer, GetBlock(h))

    def execute_sync(self):
        """ Once we've fetched all the blocks, verify they chain cleanly,
        apply them to the blockchain and update the mempool
        """
        print("Starting executing sync")
        
        sorted_blocks = sorted(self.sync_block_buffer, key=lambda item: item.height)

        # First check if all the blocks chain cleanly
        for i in range(self.sync_block_count):
            block = sorted_blocks[i]
            if i == 0:
                previous_block = self.chain[self.fork_height]
            else:
                previous_block = sorted_blocks[i - 1]

            if not verify_prev_links_cleanly(block, previous_block.block_hash):
                print(f"Dirty link on chain during sync at height {block.height}, current: {block}, previous: {previous_block}")
                self.cancel_sync()
                return
        
        print("Preoprly executing sync")
        # Add back to the mempool the blocks that will be removed due to the fork
        for block in self.chain[self.fork_height + 1:]:
            for hash in block.tx_hashes:
                tx = self.mempool_storage.get(hash)
                if tx is None:
                    print("Trying to add a nonexistend tx to the mempool, possible from another node?")
                    continue

                if not tx in self.mempool:
                    self.mempool.append(tx)

        # Create our new chain
        self.chain = self.chain[:self.fork_height + 1]
        self.chain.extend(sorted_blocks)

        # Remove transactions from our mempool that are included in the block we got
        self.mempool = [tx for tx in self.mempool if
                         compute_transaction_hash(tx) not in set([tx_hash for block in self.sync_block_buffer for tx_hash in block.tx_hashes])]

        print("Sync complete")
        self.cancel_sync()
    
    def cancel_sync(self):
        """ Clean up the variables associated with a sync and start a new
        mining task.
        """
        self.sync_block_buffer = []
        self.sync_block_count = 0
        self.sync_peer = None
        self.sync_their_height = 0
        self.fork_height = 0
        self.mining_job_id += 1
        self.start_pow_search_task()

    @lazy_wrapper(BlockResponse)
    def on_block_response(self, peer: Peer, payload: BlockResponse) ->  None:
        if peer != self.sync_peer:
            return
        block = Block(
            payload.height, 
            payload.prev_hash, 
            payload.txs_hash,
            payload.timestamp, 
            payload.difficulty, 
            payload.nonce,
            payload.block_hash,
            [payload.tx_hashes[i:i+32] for i in range(0, len(payload.tx_hashes), 32)]
        )
        #print(f"Got BlockResponse")
        height = block.height
        block.block_hash = compute_block_hash(block_to_header(block))
        if not verify_block(block):
            print(f"Invalid block during sync at height {height}")
            self.cancel_sync()
            return

        if height <= self.fork_height or height > self.fork_height + self.sync_block_count:
            print(f"Got block of invalid height {height}, fork at {self.fork_height}, expected count: {self.sync_block_count}")
            self.cancel_sync()
            return
        
        if height in [block.height for block in self.sync_block_buffer]:
            print(f"Got block with height we alreayd have {height}, {self.sync_block_buffer}")
            self.cancel_sync()
            return
        
        print(f"Got block: {block.height}, count: {len(self.sync_block_buffer)}, want: {self.sync_block_count}")
        self.sync_block_buffer.append(block)

        # Once we've gathered all the blocks, we can start the 
        if (len(self.sync_block_buffer) == self.sync_block_count):
            self.execute_sync()
       

    @lazy_wrapper(SubmitTransactionMessage)
    def on_submit_transaction(self, peer: Peer, payload: SubmitTransactionMessage) -> None:
        print(f"Received submit transaction {payload}")
        if peer.public_key.key_to_bin() not in CLIENT_KEYS:
            return

        tx = Transaction(
            payload.sender_key,
            payload.data,
            payload.timestamp,
            payload.signature
            )
        if not verify_transaction_signature(tx):
            print(f"Signature failed verification: {tx}")
            return

        tx_hash = compute_transaction_hash(tx)

        if any(compute_transaction_hash(t) == tx_hash for t in self.mempool):
            print(f"Duplicate signature: {tx}")
            return
        
        self.mempool.append(tx)
        self.mempool_storage[tx_hash] = (tx)
        

        resposne = SubmitTransactionResponseMessage(True, tx_hash,
                                    "Successfully submitted transaction")
        self.ez_send(peer, resposne)

        self.start_pow_search_task()
    
    @lazy_wrapper(GetChainHeight)
    def on_get_chain_height(self, peer: Peer, payload: GetChainHeight) -> None:
        print(f"Received GetChainHeight: {payload}")
        if peer.public_key.key_to_bin() not in CLIENT_KEYS:
            return
        
        height = len(self.chain) - 1
        tip_hash = self.chain[-1].block_hash

        response = ChainHeightResponse(
            payload.request_id,
            height,
            tip_hash,
        )

        self.ez_send(peer, response)
    
    @lazy_wrapper(GetBlock)
    def on_get_block(self, peer: Peer, payload: GetBlock) -> None:
        print(f"Got GetBlock: {payload}")
        key = peer.public_key.key_to_bin()
        if key not in PUBLIC_KEYS + CLIENT_KEYS or key in self.ignored_peers:
            return
            
        if payload.height < 0 or payload.height >= len(self.chain):
            return

        block = self.chain[payload.height]

        response = BlockResponse(
            block.height,
            block.prev_hash,
            block.txs_hash,
            block.timestamp,
            block.difficulty,
            block.nonce,
            block.block_hash,
            b"".join(block.tx_hashes)
        )
        print(f"Responding to getBlock with {response}")
        self.ez_send(peer, response)
    
    @lazy_wrapper(HashRequest)
    def on_hash_request(self, peer: Peer, payload: HashRequest):
        key = peer.public_key.key_to_bin()
        if key not in OTHER_PEER_KEYS or key in self.ignored_peers:
            return
        if payload.height < 0:
            print("Discarding request for height < 0")
            return
        print(f"Received hash request: {payload}")
        if payload.height >= len(self.chain):
            print("I'm not tall enough :(")
            return
        message = HashResponse(payload.height, self.chain[payload.height].block_hash)
        self.ez_send(peer, message)
    
    @lazy_wrapper(DoubleHashRequest)
    def on_double_hash_request(self, peer: Peer, payload: DoubleHashRequest):
        key = peer.public_key.key_to_bin()
        if key not in OTHER_PEER_KEYS or key in self.ignored_peers:
            return
        if payload.height < 0:
            print("Discarding request for height < 0")
            return
        print(f"Received hash request: {payload}")
        if payload.height >= len(self.chain):
            print("I'm not tall enough :(")
            return
        message = DoubleHashResponse(payload.height, self.chain[payload.height].block_hash, bytes(255) if payload.height == 0 else self.chain[payload.height-1].block_hash)
        self.ez_send(peer, message)

    @lazy_wrapper(HashResponse)
    def on_hash_response(self, peer: Peer, payload: HashResponse) -> None:
        if peer != self.sync_peer:
            return
        print(f"Received DoubleHashResponse: {payload}")
        
        height = payload.height
        hash = payload.hash

        if height < 0:
            print(f"No common ancestor found, something is very wrong, {height}")
            return
        
        our_hash = self.chain[height].block_hash

        # Disagreement is deeper than MAX_DISAGREEMENT_DEPTH
        if hash != our_hash:
            print("Disagreement too deep")
            self.ignored_peers.add(peer.public_key.key_to_bin())
            self.cancel_sync()
            return
        self.ez_send(peer, DoubleHashRequest(self.compute_mid()))
    
    @lazy_wrapper(DoubleHashResponse)
    def on_double_hash_response(self, peer: Peer, payload: DoubleHashResponse) -> None:
        if peer != self.sync_peer:
            return
        print(f"Received DoubleHashResponse: {payload}")
        
        height = payload.height
        hash = payload.hash
        previous_hash = payload.hash_previous

        if height < 0:
            print(f"No common ancestor found, something is very wrong, {height}")
            return

        mid: int = self.compute_mid()
        if height != mid:
            print(f"Received hash response at height: {height} different than the one we were expecting {mid}, low: {self.search_low}, high: {self.search_high}")
            return


        # Case 1: Hash is not linked to our previous block, so we are looking too high
        if height > 0 and previous_hash != self.chain[height - 1].block_hash:
            print(f"Hash at height {height} is not linked to our chain, looking lower, hash: {hash.hex()}, previous hash: {previous_hash.hex()}, expected previous hash: {self.chain[height - 1].block_hash.hex()}")
            self.search_high = mid - 1
            mid: int = self.compute_mid()
            print(f"Need to look backwards to {mid}")
            message = DoubleHashRequest(mid)
            self.ez_send(peer, message)
            return
            
        # Case 2: Hash is linked, but blocks are not equal, so we found the divergence point, we can stop the search and start syncing
        # Termination case
        elif height > 0 and previous_hash == self.chain[height - 1].block_hash and hash != self.chain[height].block_hash:
            print(f"Hash at height {height} is linked but different than ours, syncing, hash: {hash.hex()}, previous hash: {previous_hash.hex()}, expected hash: {self.chain[height].block_hash.hex()}")

        # Case 3: Hash is linked and blocks are equal, so we are looking too low
        elif height > 0: 
            self.search_low = mid + 1
            mid: int = self.compute_mid()

            print(f"Need to look forwards to {mid}")
            message = DoubleHashRequest(mid)
            self.ez_send(peer, message)
            return
        
        if height == 0 and hash != self.chain[0].block_hash:
                print(f"Disagreement about genesis block, something is very wrong, {height}")
                return
        if height == 0: height = 1

        # Found Divergence point
        print(f"Fork point at height {height}, trimming chain and syncing")

        # Stop mining until sync is completed
        self.mining_job_id += 1
        self.mining_stop_event.set()
        
        # Set variables for the sync and start it
        self.sync_block_buffer = []
        self.sync_block_count = self.sync_their_height - (height-1)
        self.fork_height = height-1
        self.sync_their_tip(peer, height, self.sync_their_height)


async def start_client() -> None:
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.add_key("me", "curve25519", KEYS_FILE)

    builder.add_overlay(
        "BlockchainEngineeringCommunity",
        "me",
        [WalkerDefinition(Strategy.RandomWalk, -1, {"timeout": 10.0})],
        default_bootstrap_defs,
        {},
        [("started",)],
    )

    ipv8 = IPv8(
        builder.finalize(),
        extra_communities={
            "BlockchainEngineeringCommunity": BlockchainEngineeringCommunity
        },
    )

    await ipv8.start()
    community = ipv8.get_overlay(BlockchainEngineeringCommunity)
    loop = asyncio.get_running_loop()
    assert community is not None

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, community.save_chain)

    await run_forever()


asyncio.run(start_client())