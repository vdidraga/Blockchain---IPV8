from asyncio import run
from dataclasses import dataclass
from dotenv import load_dotenv
from os import getenv

from ipv8.community import Community, CommunitySettings
from ipv8.configuration import ConfigBuilder, WalkerDefinition, Strategy, default_bootstrap_defs
from ipv8.util import run_forever
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import PeerObserver
from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.lazy_community import lazy_wrapper
from ipv8_service import IPv8


# Load environment variables 
GROUP_ID = getenv("GROUP_ID", "")
MY_ORDER = int(getenv("MY_ORDER", -1))
KEYS_FILE = getenv("KEYS_FILE", "")
assert "" not in [GROUP_ID, KEYS_FILE]
assert MY_ORDER != -1

COMMUNITY_ID = bytes.fromhex("4c61623247726f75705369676e696e6732303236")
SERVER_PUBLIC_KEY = bytes.fromhex("4c69624e61434c504b3a82e33614a342774e084af80835838d6dbdb64a537d3ddb6c1d82011a7f101553cda40cf5fa0e0fc23abd0a9c4f81322282c5b34566f6b8401f5f683031e60c96")
PUBLIC_KEY_1 = bytes.fromhex("4c69624e61434c504b3a6ddc887fd7a98d41126d24eb4d3349f27683c555698c94b80b0a11bb43c2f6765645e827f4c331c3eb653f1f52d38683423e6b013c25f3157ed8adbf86aa997a")
PUBLIC_KEY_2 = bytes.fromhex("4c69624e61434c504b3ae9a6f3ee192bcb9833fe647728a19e74d6b7fe2e42efe96f4de40d4922aa7a3dcb7c47a5f1776db9902548aab9fb4ef06dd1dc39b12f99f5e8326334ebe7fcd3")
PUBLIC_KEY_3 = bytes.fromhex("4c69624e61434c504b3a87ca1dee80e128d6ad389fb7b2fd1f99bfa86377fdf3815e97b734d767c48840dc818b5467b27b8fad1e434e07005e05eac40a726334a5b3a83b289a51ca097c")
PUBLIC_KEYS = [PUBLIC_KEY_1, PUBLIC_KEY_2, PUBLIC_KEY_3]

REGISTER_GROUP = False
START_PROTOCOL = False
BYPASS = False

@dataclass
class RegisterMessage(DataClassPayload[1]):
    member1_key: bytes
    member2_key: bytes
    member3_key: bytes

@dataclass
class RegisterResponseMessage(DataClassPayload[2]):
    success: bool
    group_id: str
    message: str

@dataclass
class ChallengeRequestMessage(DataClassPayload[3]):
    group_id: str

@dataclass
class ChallengeResponseMessage(DataClassPayload[4]):
    nonce: bytes
    round_number: int
    deadline: float

@dataclass
class BundleSubmissionMessage(DataClassPayload[5]):
    group_id: str
    round_number: int
    sig1: bytes
    sig2: bytes
    sig3: bytes

@dataclass
class RoundResultMessage(DataClassPayload[6]):
    success: bool
    round_number: int
    rounds_completed: int
    message: str

@dataclass
class NonceMessage(DataClassPayload[7]):
    nonce: bytes

@dataclass
class SignatureMessage(DataClassPayload[8]):
    sig: bytes

@dataclass
class PassTurnMessage(DataClassPayload[9]):
    yes: bool

@dataclass
class GroupIDMessage(DataClassPayload[10]):
    group_id: str


# Trigger dataclass payload compilation for decode-only payloads.
_ = RegisterResponseMessage(False, "", "")
_ = ChallengeResponseMessage(bytes(1), 0, 0.0)
_ = RoundResultMessage(False, 0, 0, "")
_ = NonceMessage(bytes(1))
_ = GroupIDMessage("")
_ = SignatureMessage(bytes(1))
_ = PassTurnMessage(False)

class BlockchainEngineeringCommunity(Community, PeerObserver):
    community_id = COMMUNITY_ID

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.add_message_handler(RegisterResponseMessage, self.on_register_response)
        self.add_message_handler(ChallengeResponseMessage, self.on_challenge_response)
        self.add_message_handler(RoundResultMessage, self.on_round_result)
        self.add_message_handler(NonceMessage, self.on_nonce)
        self.add_message_handler(SignatureMessage, self.on_signature)
        self.add_message_handler(PassTurnMessage, self.on_pass_turn)
        self.add_message_handler(GroupIDMessage, self.on_group_id)

        self.server = None
        self.peers: list[None | Peer] = [None] * 3

        self.sigs = [None] * 3

        self.round_number = None

    def started(self) -> None:
        print(f"Started peer")
        print(f"I am: {self.my_peer}, public key: {self.my_peer.public_key.key_to_bin().hex()}")
        self.network.add_peer_observer(self)

        self.peers[MY_ORDER-1] = self.my_peer
        
        # Periodic task to keep searching for all peers
        async def discover_all_peers() -> None:
            if None not in self.peers and self.server is not None:
                self.cancel_pending_task("discover_all_peers")
                return
            # Force a check by querying all known peers
            all_known = self.get_peers()
            print(f"Known peers: {len(all_known)}, have all: {None not in self.peers and self.server is not None}")
        
        self.register_task("discover_all_peers", discover_all_peers, interval=2.0, delay=0)

    def on_peer_added(self, peer: Peer) -> None:
        peer_key = peer.public_key.key_to_bin()

        print(f"I found: {peer_key.hex()}")

        if peer_key == SERVER_PUBLIC_KEY:
            print("Found server!")
            self.server = peer

            if BYPASS:
                self.ez_send(self.server, RegisterMessage(PUBLIC_KEY_1, PUBLIC_KEY_2, PUBLIC_KEY_3))


        if peer_key == PUBLIC_KEY_1:
            print("Found peer1!")
            self.peers[0] = peer
        elif peer_key == PUBLIC_KEY_2:
            print("Found peer2!")
            self.peers[1] = peer
        elif peer_key == PUBLIC_KEY_3:
            print("Found peer3!")
            self.peers[2] = peer
        
        if None not in self.peers and self.server is not None:
            print("Ready to start")
            if REGISTER_GROUP:
                self.ez_send(self.server, RegisterMessage(PUBLIC_KEY_1, PUBLIC_KEY_2, PUBLIC_KEY_3))
            elif START_PROTOCOL:
                self.ez_send(self.server, ChallengeRequestMessage(GROUP_ID))

        
    
    def on_peer_removed(self, peer: Peer) -> None:
        pass
    
    @lazy_wrapper(RegisterResponseMessage)
    def on_register_response(self, peer: Peer, payload: RegisterResponseMessage) -> None:
        if peer.public_key.key_to_bin() != SERVER_PUBLIC_KEY:
            return
        
        print(payload)
        self.send_to_others(GroupIDMessage(payload.group_id))

        # Handle groupid yourself
        global GROUP_ID
        GROUP_ID = payload.group_id
        if START_PROTOCOL:
            assert self.server is not None
            self.ez_send(self.server, ChallengeRequestMessage(GROUP_ID))

    
    @lazy_wrapper(ChallengeResponseMessage)
    def on_challenge_response(self, peer: Peer, payload: ChallengeResponseMessage) -> None:
        if peer.public_key.key_to_bin() != SERVER_PUBLIC_KEY:
            return
        self.round_number = payload.round_number
        print(payload)
        self.send_to_others(NonceMessage(payload.nonce))

        # Handle nonce yourself
        sig = self.crypto.create_signature(self.my_peer.key, payload.nonce)
        self.sigs[MY_ORDER-1] = sig
        all_sigs = all(sig is not None for sig in self.sigs)
        if all_sigs:
            self.ez_send(self.server,
                         BundleSubmissionMessage(GROUP_ID, self.round_number, self.sigs[0], self.sigs[1], self.sigs[2]))
    

    @lazy_wrapper(RoundResultMessage)
    def on_round_result(self, peer: Peer, payload: RoundResultMessage) -> None:
        print("Got RoundResult")
        if peer.public_key.key_to_bin() != SERVER_PUBLIC_KEY:
            return
        print(payload)

        if not payload.success:
            print("Failure :(")
            return

        if payload.rounds_completed == 1:
            print("Passing to node 2")
            self.ez_send(self.peers[1], PassTurnMessage(True))
        elif payload.rounds_completed == 2:
            print("Passing to node 3")
            self.ez_send(self.peers[2], PassTurnMessage(True))
        elif payload.rounds_completed == 3:
            print("Finished!")
    
    @lazy_wrapper(PassTurnMessage)
    def on_pass_turn(self, peer: Peer, payload: RoundResultMessage) -> None:
        print("Got PassTurn")
        if peer.public_key.key_to_bin() not in PUBLIC_KEYS:
            return
        print(payload)
        assert self.server is not None
        self.ez_send(self.server, ChallengeRequestMessage(GROUP_ID))
    
    @lazy_wrapper(NonceMessage)
    def on_nonce(self, peer: Peer, payload: NonceMessage) -> None:
        print("Got Nonce")
        if peer.public_key.key_to_bin() not in PUBLIC_KEYS:
            return
        print(payload)
        sig = self.crypto.create_signature(self.my_peer.key, payload.nonce)
        self.ez_send(peer, SignatureMessage(sig))
    
    @lazy_wrapper(SignatureMessage)
    def on_signature(self, peer: Peer, payload: SignatureMessage) -> None:
        print("Got Signature")
        if peer.public_key.key_to_bin() not in PUBLIC_KEYS:
            return
        print(payload)

        peer_key = peer.public_key.key_to_bin()

        if peer_key == PUBLIC_KEY_1:
            self.sigs[0] = payload.sig
        elif peer_key == PUBLIC_KEY_2:
            self.sigs[1] = payload.sig
        elif peer_key == PUBLIC_KEY_3:
            self.sigs[2] = payload.sig
        
        all_sigs = all(sig is not None for sig in self.sigs)
        if all_sigs:
            self.ez_send(self.server,
                         BundleSubmissionMessage(GROUP_ID, self.round_number, self.sigs[0], self.sigs[1], self.sigs[2]))
    
    @lazy_wrapper(GroupIDMessage)
    def on_group_id(self, peer: Peer, payload: GroupIDMessage) -> None:
        print("Got GroupID")
        if peer.public_key.key_to_bin() not in PUBLIC_KEYS:
            return
        global GROUP_ID
        GROUP_ID = payload.group_id
        print(payload)

        if START_PROTOCOL:
            assert self.server is not None
            self.ez_send(self.server, ChallengeRequestMessage(GROUP_ID))
        

    def send_to_others(self, payload: DataClassPayload) -> None:
        for p in self.peers:
            if p is None:
                print(f"None peer in sending: {payload}")
                continue
            if p == self.my_peer:
                continue
            self.ez_send(p, payload)
            


async def start_client() -> None:
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.add_key("me", "curve25519", KEYS_FILE)

    builder.add_overlay(
        "BlockchainEngineeringCommunity",
        "me",
        [WalkerDefinition(Strategy.RandomWalk, -1, {"timeout": 3.0})],
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


    builder.add_overlay("BlockchainEngineeringCommunity",
                        "me",
                        [WalkerDefinition(Strategy.RandomWalk, 10, {"timeout": 10.0})], 
                        default_bootstrap_defs, {}, [("started",)])
    
    await IPv8(builder.finalize(),
               extra_communities={"BlockchainEngineeringCommunity": BlockchainEngineeringCommunity}).start()
    
    await run_forever()


run(start_client())