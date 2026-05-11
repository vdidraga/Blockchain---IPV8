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
        self.network.add_peer_observer(self)

    def on_peer_added(self, peer: Peer) -> None:
        print(f"I am: {self.my_peer}, I found: {peer.public_key.key_to_bin().hex()}")

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