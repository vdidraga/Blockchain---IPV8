from asyncio import run
from dataclasses import dataclass

from ipv8.community import Community, CommunitySettings
from ipv8.configuration import (
    ConfigBuilder,
    WalkerDefinition,
    Strategy,
    default_bootstrap_defs,
)
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import PeerObserver
from ipv8.util import run_forever
from ipv8_service import IPv8


COMMUNITY_ID = bytes.fromhex(
    "4c616233426c6f636b636861696e323032365057"
)
OUR_COMMUNITY_ID = bytes.fromhex(
    "4c61623247726f75705369676e696e67323032a1"
)
SERVER_PUBLIC_KEY = bytes.fromhex(
    "4c69624e61434c504b3ae3fc099fb56ca3b5e1de9a1c843387f2acdbb78b1bd4350ffde518068a0d246344b10d0d8c355fd0d76873e7d7f7838f3715e025af08f791324495e083331ce6"
)
# GROUP_ID = "a6edc7f90a618bd8"
GROUP_ID = "f9e7dc3ac7b0a791"
KEYS_FILE = "myKeys.pem"


@dataclass
class RegisterBlockchain(DataClassPayload[1]):
    group_id: str
    community_id: bytes


@dataclass
class RegisterResponse(DataClassPayload[2]):
    success: bool
    message: str


# Force payload compilation.
_ = RegisterBlockchain("", bytes(0))
_ = RegisterResponse(False, "")


class RegistrationCommunity(Community, PeerObserver):

    community_id = COMMUNITY_ID

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)

        self.add_message_handler(
            RegisterResponse,
            self.on_register_response
        )

        # Known peers.
        self.peers = set()

    def started(self) -> None:

        print("Registration community started")
        print(
            "My public key:",
            self.my_peer.public_key.key_to_bin().hex()
        )

        # Enable peer discovery callbacks.
        self.network.add_peer_observer(self)


    def on_peer_added(self, peer: Peer) -> None:

        # Ignore myself.
        if peer == self.my_peer:
            return

        # Avoid duplicates.
        if peer in self.peers:
            return

        self.peers.add(peer)

        print(f"Discovered peer: {peer.address}")

        # Send my registration message.
        if peer.public_key.key_to_bin() == SERVER_PUBLIC_KEY:
            print("Sending registrataion to server")
            self.ez_send(
                peer,
                RegisterBlockchain(GROUP_ID, OUR_COMMUNITY_ID)
            )

    def on_peer_removed(self, peer: Peer) -> None:

        if peer in self.peers:
            self.peers.remove(peer)

        print(f"Peer removed: {peer.address}")


    @lazy_wrapper(RegisterResponse)
    def on_register_response(
        self,
        peer: Peer,
        payload: RegisterResponse,
    ) -> None:
        if peer.public_key.key_to_bin() != SERVER_PUBLIC_KEY:
            print("Received a non-server message, skipping")
            return
        
        print(payload)


async def start_client() -> None:

    builder = (
        ConfigBuilder()
        .clear_keys()
        .clear_overlays()
    )

    builder.add_key(
        "me",
        "curve25519",
        KEYS_FILE,
    )

    builder.add_overlay(
        "RegistrationCommunity",
        "me",
        [
            WalkerDefinition(
                Strategy.RandomWalk,
                50,
                {"timeout": 3.0},
            )
        ],
        default_bootstrap_defs,
        {},
        [("started",)],
    )

    await IPv8(
        builder.finalize(),
        extra_communities={
            "RegistrationCommunity":
                RegistrationCommunity
        },
    ).start()

    await run_forever()


run(start_client())