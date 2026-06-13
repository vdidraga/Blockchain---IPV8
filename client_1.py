<<<<<<< HEAD
from asyncio import run
from dataclasses import dataclass

from ipv8.community import Community, CommunitySettings
from ipv8.configuration import ConfigBuilder, WalkerDefinition, Strategy, default_bootstrap_defs
from ipv8.util import run_forever
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import PeerObserver
from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.lazy_community import lazy_wrapper
from ipv8_service import IPv8

from nonce_finder import do_challenge, EMAIL, GITHUB_URL

COMMUNITY_ID = "2c1cc6e35ff484f99ebdfb6108477783c0102881"
SERVER_PUBLIC_KEY = "4c69624e61434c504b3a86b23934a28d669c390e2d1fc0b0870706c4591cc0cb178bc5a811da6d87d27ef319b2638ef60cc8d119724f4c53a1ebfad919c3ac4136c501ce5c09364e0ebb"


@dataclass
class SubmissionMessage(DataClassPayload[1]):
    email: str
    github_url: str
    nonce: int

@dataclass
class SubmissionResponse(DataClassPayload[2]):
    success: bool
    message: str


# Trigger dataclass payload compilation for decode-only payloads.
_ = SubmissionResponse(False, "")

class BlockchainEngineeringCommunity(Community, PeerObserver):
    community_id = bytes.fromhex(COMMUNITY_ID)

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.add_message_handler(SubmissionResponse, self.on_submission_response)

        self.server = None

    def started(self) -> None:
        print(f"Started peer")
        print(f"I am: {self.my_peer}, public key: {self.my_peer.public_key.key_to_bin().hex()}")
        self.network.add_peer_observer(self)

    def on_peer_added(self, peer: Peer) -> None:
        print(f"I found: {peer.public_key.key_to_bin().hex()}")

        if peer.public_key.key_to_bin() == bytes.fromhex(SERVER_PUBLIC_KEY):
            print(f"Found server!")
            self.server = peer

            self.send_challenge()
    
    def on_peer_removed(self, peer: Peer) -> None:
        pass

    
    def send_challenge(self) -> None:
        print(f"Starting challenge to server")
        assert self.server is not None
        nonce = do_challenge(28)
        message = SubmissionMessage(EMAIL, GITHUB_URL, nonce)
        print(f"Sending message {message}")
        self.ez_send(self.server, message)
    
    @lazy_wrapper(SubmissionResponse)
    def on_submission_response(self, peer: Peer, payload: SubmissionResponse) -> None:
        print(payload)


async def start_client() -> None:
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.add_key("me", "curve25519", "myKeys.pem")

    builder.add_overlay("BlockchainEngineeringCommunity",
                        "me",
                        [WalkerDefinition(Strategy.RandomWalk, 10, {"timeout": 3.0})], 
                        default_bootstrap_defs, {}, [("started",)])
    
    await IPv8(builder.finalize(),
               extra_communities={"BlockchainEngineeringCommunity": BlockchainEngineeringCommunity}).start()
    
    await run_forever()


run(start_client())
=======
import asyncio
from pathlib import Path
from dataclasses import dataclass
from ipv8.keyvault.crypto import default_eccrypto
from pathlib import Path
from ipv8.community import Community, CommunitySettings
from ipv8.configuration import (
    ConfigBuilder,
    Strategy,
    WalkerDefinition,
    default_bootstrap_defs
)
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.payload_dataclass import DataClassPayload, type_from_format
from ipv8.peer import Peer
from ipv8_service import IPv8
from os import getenv
from dotenv import load_dotenv

from mine import mine

varlenHutf8 = type_from_format("varlenHutf8")

load_dotenv()
KEYS_FILE = getenv("KEYS_FILE")
assert KEYS_FILE

COMMUNITY_ID = bytes.fromhex("2c1cc6e35ff484f99ebdfb6108477783c0102881")
SERVER_KEY_BYTES = bytes.fromhex("4c69624e61434c504b3a86b23934a28d669c390e2d1fc0b0870706c4591cc0cb178bc5a811da6d87d27ef319b2638ef60cc8d119724f4c53a1ebfad919c3ac4136c501ce5c09364e0ebb")
RESEND_INTERVAL = 10.0


EMAIL = "v.a.didraga@student.tudelft.nl"
GITHUB_URL = "https://github.com/vdidraga/Blockchain---IPV8"


@dataclass
class SubmissionPayload(DataClassPayload[1]):
    email: varlenHutf8
    github_url: varlenHutf8
    nonce: int

@dataclass
class ResponsePayload(DataClassPayload[2]):
    success: bool
    message: varlenHutf8

_ = ResponsePayload(False, "")

class Lab1Community(Community):
    community_id = COMMUNITY_ID

    def __init__(self, settings: CommunitySettings) -> None:
        super().__init__(settings)
        self.add_message_handler(ResponsePayload, self.on_response)
        self.done: asyncio.Future = asyncio.Future()
        self.email = ""
        self.github_url = ""
        self.nonce = 0

    def started(self):
        key = default_eccrypto.key_from_private_bin(Path("key.pem").read_bytes())
        print(key.pub().key_to_bin().hex())
        self.register_task("submit_loop", self._submit_loop)

    async def _submit_loop(self):
        try_num = 0
        while not self.done.done():
            server = self._find_server()
            if server is None:
                await asyncio.sleep(RESEND_INTERVAL)
                continue

            try_num += 1
            if try_num == 1:
                print("Sending")
            else:
                print(f"Resending {try_num}")
                
            self.ez_send(server, SubmissionPayload( email=self.email, github_url=self.github_url, nonce=self.nonce))

            await asyncio.sleep(RESEND_INTERVAL)

    def _find_server(self):
        for peer in self.get_peers():
            if peer.public_key.key_to_bin() == SERVER_KEY_BYTES:
                return peer
        return None

    @lazy_wrapper(ResponsePayload)
    def on_response(self, peer: Peer, payload: ResponsePayload):
        if peer.public_key.key_to_bin() != SERVER_KEY_BYTES:
            return
        print(payload)
        if not self.done.done():
            self.done.set_result(True)


async def main():
    key = Path(KEYS_FILE)
    if not key.exists():
        key.write_bytes(default_eccrypto.generate_key("curve25519").key_to_bin())

    builder = (
        ConfigBuilder().clear_keys().clear_overlays()
        .add_key("my_key", "curve25519", KEYS_FILE)
        .add_overlay(
            "Lab1Community",
            "my_key",
            [WalkerDefinition(Strategy.RandomWalk, 10, {"timeout": 3.0})],
            default_bootstrap_defs,
            {},
            [("started",)],
        )
    )

    instance = IPv8(builder.finalize(), extra_communities={"Lab1Community": Lab1Community})
    community = instance.get_overlay(Lab1Community)
    community.email = EMAIL
    community.github_url = GITHUB_URL
    community.nonce = mine()

    await instance.start()
    try:
        await community.done
    except asyncio.CancelledError:
        pass
    finally:
        await instance.stop()


if __name__ == "__main__":
    asyncio.run(main())
>>>>>>> bfe7d47 (Team work makes the dream work)
