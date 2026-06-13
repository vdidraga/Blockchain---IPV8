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
GROUP_ID = getenv("GROUP_ID")
MY_ORDER = int(getenv("MY_ORDER"))
KEYS_FILE = getenv("KEYS_FILE")
assert GROUP_ID and MY_ORDER and KEYS_FILE

COMMUNITY_ID = bytes.fromhex("4c61623247726f75705369676e696e6732303236")

SERVER_PUBLIC_KEY = bytes.fromhex("4c69624e61434c504b3a82e33614a342774e084af80835838d6dbdb64a537d3ddb6c1d82011a7f101553cda40cf5fa0e0fc23abd0a9c4f81322282c5b34566f6b8401f5f683031e60c96")

PUBLIC_KEY_1 = bytes.fromhex("4c69624e61434c504b3a6ddc887fd7a98d41126d24eb4d3349f27683c555698c94b80b0a11bb43c2f6765645e827f4c331c3eb653f1f52d38683423e6b013c25f3157ed8adbf86aa997a")
PUBLIC_KEY_2 = bytes.fromhex("4c69624e61434c504b3aea247287365cefd9dfb2bc0916f6b48cc92fb538ba6de6d4e48bc963e53ec457f55086c09ef0141d8b82305528915235be3166e967dc50e0d6c13d8a91108670")
PUBLIC_KEY_3 = bytes.fromhex("4c69624e61434c504b3a87ca1dee80e128d6ad389fb7b2fd1f99bfa86377fdf3815e97b734d767c48840dc818b5467b27b8fad1e434e07005e05eac40a726334a5b3a83b289a51ca097c")

PUBLIC_KEYS = [PUBLIC_KEY_1, PUBLIC_KEY_2, PUBLIC_KEY_3]


REGISTER_GROUP = False
START_PROTOCOL = False

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
    round_number: int
    nonce: bytes


@dataclass
class SignatureMessage(DataClassPayload[8]):
    round_number: int
    sig: bytes


@dataclass
class PassTurnMessage(DataClassPayload[9]):
    yes: bool


@dataclass
class GroupIDMessage(DataClassPayload[10]):
    group_id: str


@dataclass
class ReadyMessage(DataClassPayload[11]):
    yes: bool


# Trigger dataclass payload compilation.
_ = RegisterResponseMessage(False, "", "")
_ = ChallengeResponseMessage(bytes(32), 0, 0.0)
_ = RoundResultMessage(False, 0, 0, "")
_ = NonceMessage(0, bytes(32))
_ = SignatureMessage(0, bytes(64))
_ = PassTurnMessage(False)
_ = GroupIDMessage("")
_ = ReadyMessage(False)


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
        self.add_message_handler(ReadyMessage, self.on_ready)

        self.server = None
        self.peers = [None] * 3
        self.ready = [False] * 3

        self.sigs = [None] * 3
        self.round_number = None

        self.local_ready_sent = False
        self.initial_action_done = False
        self.submitted_rounds = set()

    def started(self) -> None:
        print("Started peer")
        print("I am public key:", self.my_peer.public_key.key_to_bin().hex())

        self.network.add_peer_observer(self)

        self.peers[MY_ORDER - 1] = self.my_peer

    def on_peer_added(self, peer: Peer) -> None:
        peer_key = peer.public_key.key_to_bin()

        print("I found:", peer_key.hex())

        if peer_key == SERVER_PUBLIC_KEY:
            print("Found server!")
            self.server = peer

        elif peer_key == PUBLIC_KEY_1:
            print("Found peer1!")
            self.peers[0] = peer

        elif peer_key == PUBLIC_KEY_2:
            print("Found peer2!")
            self.peers[1] = peer

        elif peer_key == PUBLIC_KEY_3:
            print("Found peer3!")
            self.peers[2] = peer

        self.maybe_announce_ready()

    def on_peer_removed(self, peer: Peer) -> None:
        pass

    def maybe_announce_ready(self) -> None:
        if self.local_ready_sent:
            return

        if self.server is None:
            return

        if any(p is None for p in self.peers):
            return

        self.local_ready_sent = True
        self.ready[MY_ORDER - 1] = True

        print("I am locally ready. Sending ReadyMessage.")
        self.send_to_others(ReadyMessage(True))

        self.maybe_start_initial_action()

    def mark_ready(self, peer_key: bytes) -> None:
        if peer_key == PUBLIC_KEY_1:
            self.ready[0] = True
        elif peer_key == PUBLIC_KEY_2:
            self.ready[1] = True
        elif peer_key == PUBLIC_KEY_3:
            self.ready[2] = True

    def all_ready(self) -> bool:
        return all(self.ready)

    def maybe_start_initial_action(self) -> None:
        if self.initial_action_done:
            return

        if not self.all_ready():
            print("Waiting for all ready:", self.ready)
            return

        # Only member 1 starts the whole protocol.
        if MY_ORDER != 1:
            print("All ready. Waiting for my turn.")
            return

        self.initial_action_done = True

        print("All 3 ready.")

        if REGISTER_GROUP:
            print("Registering group...")
            self.ez_send(
                self.server,
                RegisterMessage(PUBLIC_KEY_1, PUBLIC_KEY_2, PUBLIC_KEY_3),
            )
        elif START_PROTOCOL:
            print("Requesting round 1 challenge...")
            self.ez_send(self.server, ChallengeRequestMessage(GROUP_ID))

    def send_to_others(self, payload: DataClassPayload) -> None:
        for p in self.peers:
            if p is None:
                continue
            if p == self.my_peer:
                continue
            self.ez_send(p, payload)

    def maybe_submit_bundle(self) -> None:
        if self.round_number is None:
            return

        if MY_ORDER != self.round_number:
            return

        if self.round_number in self.submitted_rounds:
            return

        if not all(sig is not None for sig in self.sigs):
            return

        print(f"Submitting bundle for round {self.round_number}")

        self.submitted_rounds.add(self.round_number)

        self.ez_send(
            self.server,
            BundleSubmissionMessage(
                GROUP_ID,
                self.round_number,
                self.sigs[0],
                self.sigs[1],
                self.sigs[2],
            ),
        )

    @lazy_wrapper(RegisterResponseMessage)
    def on_register_response(self, peer: Peer, payload: RegisterResponseMessage) -> None:
        if peer.public_key.key_to_bin() != SERVER_PUBLIC_KEY:
            return

        print("RegisterResponse:", payload)

        if not payload.success:
            print("Registration failed.")
            return

        global GROUP_ID
        GROUP_ID = payload.group_id

        self.send_to_others(GroupIDMessage(GROUP_ID))

        if MY_ORDER == 1 and START_PROTOCOL:
            print("Requesting round 1 challenge...")
            self.ez_send(self.server, ChallengeRequestMessage(GROUP_ID))

    @lazy_wrapper(GroupIDMessage)
    def on_group_id(self, peer: Peer, payload: GroupIDMessage) -> None:
        if peer.public_key.key_to_bin() not in PUBLIC_KEYS:
            return

        global GROUP_ID
        GROUP_ID = payload.group_id

        print("Got GroupID:", GROUP_ID)

        # Do NOT start here unless you are member 1 and explicitly configured to start.
        if MY_ORDER == 1 and START_PROTOCOL and not self.initial_action_done:
            self.initial_action_done = True
            self.ez_send(self.server, ChallengeRequestMessage(GROUP_ID))

    @lazy_wrapper(ReadyMessage)
    def on_ready(self, peer: Peer, payload: ReadyMessage) -> None:
        peer_key = peer.public_key.key_to_bin()

        if peer_key not in PUBLIC_KEYS:
            return

        print("Got ReadyMessage from:", peer_key.hex())

        self.mark_ready(peer_key)
        self.maybe_start_initial_action()

    @lazy_wrapper(ChallengeResponseMessage)
    def on_challenge_response(self, peer: Peer, payload: ChallengeResponseMessage) -> None:
        if peer.public_key.key_to_bin() != SERVER_PUBLIC_KEY:
            return

        print("ChallengeResponse:", payload)

        self.round_number = payload.round_number
        self.sigs = [None] * 3

        # Sign locally.
        my_sig = self.crypto.create_signature(self.my_peer.key, payload.nonce)
        self.sigs[MY_ORDER - 1] = my_sig

        # Send nonce to the other two members.
        self.send_to_others(NonceMessage(payload.round_number, payload.nonce))

        self.maybe_submit_bundle()

    @lazy_wrapper(NonceMessage)
    def on_nonce(self, peer: Peer, payload: NonceMessage) -> None:
        if peer.public_key.key_to_bin() not in PUBLIC_KEYS:
            return

        print(f"Got nonce for round {payload.round_number}")

        self.round_number = payload.round_number

        sig = self.crypto.create_signature(self.my_peer.key, payload.nonce)

        # Send signature back to the round submitter.
        self.ez_send(peer, SignatureMessage(payload.round_number, sig))

    @lazy_wrapper(SignatureMessage)
    def on_signature(self, peer: Peer, payload: SignatureMessage) -> None:
        peer_key = peer.public_key.key_to_bin()

        if peer_key not in PUBLIC_KEYS:
            return

        if payload.round_number != self.round_number:
            print("Ignoring signature for wrong round")
            return

        print(f"Got signature for round {payload.round_number}")

        if peer_key == PUBLIC_KEY_1:
            self.sigs[0] = payload.sig
        elif peer_key == PUBLIC_KEY_2:
            self.sigs[1] = payload.sig
        elif peer_key == PUBLIC_KEY_3:
            self.sigs[2] = payload.sig

        self.maybe_submit_bundle()

    @lazy_wrapper(RoundResultMessage)
    def on_round_result(self, peer: Peer, payload: RoundResultMessage) -> None:
        if peer.public_key.key_to_bin() != SERVER_PUBLIC_KEY:
            return

        print("RoundResult:", payload)

        if not payload.success:
            print("Failure:", payload.message)
            return

        if payload.rounds_completed == 1:
            print("Passing turn to member 2")
            self.ez_send(self.peers[1], PassTurnMessage(True))

        elif payload.rounds_completed == 2:
            print("Passing turn to member 3")
            self.ez_send(self.peers[2], PassTurnMessage(True))

        elif payload.rounds_completed == 3:
            print("Finished all rounds!")

    @lazy_wrapper(PassTurnMessage)
    def on_pass_turn(self, peer: Peer, payload: PassTurnMessage) -> None:
        if peer.public_key.key_to_bin() not in PUBLIC_KEYS:
            return

        print(f"Got PassTurn. I am member {MY_ORDER}, requesting challenge.")

        self.ez_send(self.server, ChallengeRequestMessage(GROUP_ID))


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

    await run_forever()


run(start_client())
