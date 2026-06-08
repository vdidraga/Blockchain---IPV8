import asyncio
from dataclasses import dataclass
from ipv8.community import Community, CommunitySettings
from ipv8.configuration import ConfigBuilder, WalkerDefinition, Strategy, default_bootstrap_defs
from ipv8.util import run_forever
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import PeerObserver
from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.lazy_community import lazy_wrapper
from ipv8_service import IPv8

from client3_miner import *
from typing import List
import threading


# Already changed, ours now
COMMUNITY_ID = bytes.fromhex("4c61623247726f75705369676e696e67323032a6")

SERVER_PUBLIC_KEY = bytes.fromhex(
    "4c69624e61434c504b3ae3fc099fb56ca3b5e1de9a1c843387f2acdbb78b1bd4350ffde518068a0d246344b10d0d8c355fd0d76873e7d7f7838f3715e025af08f791324495e083331ce6"
)

PUBLIC_KEY_1 = bytes.fromhex(
    "4c69624e61434c504b3a6ddc887fd7a98d41126d24eb4d3349f27683c555698c94b80b0a11bb43c2f6765645e827f4c331c3eb653f1f52d38683423e6b013c25f3157ed8adbf86aa997a"
)
# NEW JACEK PUBLIC KEY
# PUBLIC_KEY_2 = bytes.fromhex(
#     "4c69624e61434c504b3aea247287365cefd9dfb2bc0916f6b48cc92fb538ba6de6d4e48bc963e53ec457f55086c09ef0141d8b82305528915235be3166e967dc50e0d6c13d8a91108670"
# )
# OLD JACEK PUBLIC KEY
PUBLIC_KEY_2 = bytes.fromhex(
    "4c69624e61434c504b3ae9a6f3ee192bcb9833fe647728a19e74d6b7fe2e42efe96f4de40d4922aa7a3dcb7c47a5f1776db9902548aab9fb4ef06dd1dc39b12f99f5e8326334ebe7fcd3"
)
PUBLIC_KEY_3 = bytes.fromhex(
    "4c69624e61434c504b3a87ca1dee80e128d6ad389fb7b2fd1f99bfa86377fdf3815e97b734d767c48840dc818b5467b27b8fad1e434e07005e05eac40a726334a5b3a83b289a51ca097c"
)

PUBLIC_KEYS = [PUBLIC_KEY_1, PUBLIC_KEY_2, PUBLIC_KEY_3]
GROUP_ID = "a6edc7f90a618bd8"
DIFFICULTY = 24

MY_ORDER = 2

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

        self.server = None
        self.peers: dict[bytes, Peer] = {}
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

    def started(self) -> None:
        print("Started peer")
        print("I am public key:", self.my_peer.public_key.key_to_bin().hex())

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
            
        
        print(f"Current peers state: {[p.address if p else None for p in self.peers.values()]}")
        print(f"Server: {self.server.address if self.server else None}")

    def on_peer_removed(self, peer: Peer) -> None:
        key = peer.public_key.key_to_bin()
        if key == SERVER_PUBLIC_KEY:
            self.server = None
        self.peers.pop(key, None)

    def send_to_others(self, payload: DataClassPayload) -> None:
        for peer in self.peers.values():
            self.ez_send(peer, payload)
        
    
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
        # if not self.mempool:
        #     print("Empty mempool")
        #     #return
        
        block = mine_block_with_stop(
            len(self.chain),
            self.chain[-1].block_hash,
            self.mempool,
            DIFFICULTY,
            job_id,
            lambda: stop_event.is_set() or job_id != self.mining_job_id
        )

        if block is None:
            print("None block!?!?")
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

        self.send_to_others(message)
        print("finished mining")
        self.start_pow_search_task()

    @lazy_wrapper(BlockBroadcastMessage)
    def on_block_broadcast(self, peer: Peer, payload: BlockBroadcastMessage) -> None:
        if peer.public_key.key_to_bin() not in PUBLIC_KEYS:
            print("Received block broadcast from unknown peer")
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

        if not verify_block(block):
            print(f"Received invalid block: {block}")
            return
        
        if not verify_prev_links_cleanly(block, self.chain[-1].block_hash):
            print("Received block from different chain")

            if block.height < len(self.chain)-1:
                print("Received unlinked block is behind, ignoring")
                return
            
            elif block.height == len(self.chain)-1:
                print("Received unlinked block is at the same level as ours, ignoring")
                return
            
            elif block.height > len(self.chain)-1:
                print("Received unlinked block is ahead of ours, adopting")
                if len(self.chain) < 2:
                    print("They are disagreeing about the genesis block?")
                    return None
                self.ez_send(peer, HashRequest(len(self.chain)-1))
                self.sync_peer = peer
                self.sync_their_height = block.height
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
        height = block.height
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
        if peer.public_key.key_to_bin() != SERVER_PUBLIC_KEY:
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
        print(f"Received GetChainHeight: {payload}, my height: {len(self.chain) - 1}")
        if peer.public_key.key_to_bin() != SERVER_PUBLIC_KEY:
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
        print(f"Got GetBloCK: {payload}")
        key = peer.public_key.key_to_bin()
        if key != SERVER_PUBLIC_KEY and key not in OTHER_PEER_KEYS:
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

        self.ez_send(peer, response)
    
    @lazy_wrapper(HashRequest)
    def on_hash_request(self, peer: Peer, payload: HashRequest):
        if peer.public_key.key_to_bin() not in OTHER_PEER_KEYS:
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
    
    @lazy_wrapper(HashResponse)
    def on_hash_response(self, peer: Peer, payload: HashResponse) -> None:
        if peer.public_key.key_to_bin() not in OTHER_PEER_KEYS:
            return
        print(f"Received HashResponse: {payload}")
        
        height = payload.height
        hash = payload.hash

        if height < 0:
            print(f"No common ancestor found, something is very wrong, {height}")
            return

        if height >= len(self.chain) or self.chain[height].block_hash != hash: 
            if height == 0:
                print(f"No common ancestor found, something is very wrong, {height}")
                return

            print(f"Need to look backwards to {height-1}")
            message = HashRequest(height-1)
            self.ez_send(peer, message)
            return
        
        # Found Divergence point
        print(f"Fork point at height {height}, trimming chain and syncing")

        # Stop mining until sync is completed
        self.mining_job_id += 1
        self.mining_stop_event.set()
        
        # Set variables for the sync and start it
        self.sync_block_buffer = []
        self.sync_block_count = self.sync_their_height - height
        self.fork_height = height
        self.sync_their_tip(peer, height + 1, self.sync_their_height)


async def start_client() -> None:
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.add_key("me", "curve25519", "myKeys.pem")

    builder.add_overlay(
        "BlockchainEngineeringCommunity",
        "me",
        [WalkerDefinition(Strategy.RandomWalk, -1, {"timeout": 10.0})],
        default_bootstrap_defs,
        {},
        [("started",)],
    )

    await IPv8(
        builder.finalize(),
        extra_communities={
            "BlockchainEngineeringCommunity": BlockchainEngineeringCommunity
        },
    ).start()

    await run_forever()


asyncio.run(start_client())