from types import SimpleNamespace
import importlib


def load_blockchain(monkeypatch):
	monkeypatch.setenv("CLIENT_3_COMMUNITY_ID", "00" * 32)
	monkeypatch.setenv("GROUP_ID", "1")
	monkeypatch.setenv("MY_ORDER", "1")
	monkeypatch.setenv("KEYS_FILE", "/tmp/dummy-keys")

	monkeypatch.setattr("asyncio.run", lambda coro: None)

	import client_3_blockchain
	importlib.reload(client_3_blockchain)

	return client_3_blockchain

def test_on_peer_added_tracks_server_and_peer(monkeypatch):
	blockchain = load_blockchain(monkeypatch)

	community = blockchain.BlockchainEngineeringCommunity.__new__(
		blockchain.BlockchainEngineeringCommunity
	)
	community.server = None
	community.peers = {}

	server_peer = SimpleNamespace(
		public_key=SimpleNamespace(
			key_to_bin=lambda: blockchain.SERVER_PUBLIC_KEY
		),
		address=("127.0.0.1", 1234),
	)

	other_key = next(iter(blockchain.OTHER_PEER_KEYS))
	other_peer = SimpleNamespace(
		public_key=SimpleNamespace(
			key_to_bin=lambda: other_key
		),
		address=("127.0.0.1", 4321),
	)

	blockchain.BlockchainEngineeringCommunity.on_peer_added(
		community, server_peer
	)
	blockchain.BlockchainEngineeringCommunity.on_peer_added(
		community, other_peer
	)

	assert community.server is server_peer
	assert community.peers[other_key] is other_peer

def test_on_peer_removed(monkeypatch):
	blockchain = load_blockchain(monkeypatch)

	community = blockchain.BlockchainEngineeringCommunity.__new__(
		blockchain.BlockchainEngineeringCommunity
	)

	key = next(iter(blockchain.OTHER_PEER_KEYS))

	peer = SimpleNamespace(
		public_key=SimpleNamespace(key_to_bin=lambda: key),
		address=("127.0.0.1", 1234),
	)

	community.peers = {key: peer}

	blockchain.BlockchainEngineeringCommunity.on_peer_removed(
		community, peer
	)

	assert key not in community.peers

def test_compute_mid(monkeypatch):
	blockchain = load_blockchain(monkeypatch)

	community = blockchain.BlockchainEngineeringCommunity.__new__(
		blockchain.BlockchainEngineeringCommunity
	)

	community.search_low = 10
	community.search_high = 20

	assert community.compute_mid() == 15

def test_compute_mid_single_value(monkeypatch):
	blockchain = load_blockchain(monkeypatch)

	community = blockchain.BlockchainEngineeringCommunity.__new__(
		blockchain.BlockchainEngineeringCommunity
	)

	community.search_low = 5
	community.search_high = 5

	assert community.compute_mid() == 5

def test_compute_mid_odd(monkeypatch):
	blockchain = load_blockchain(monkeypatch)

	community = blockchain.BlockchainEngineeringCommunity.__new__(
		blockchain.BlockchainEngineeringCommunity
	)

	community.search_low = 0
	community.search_high = 9

	assert community.compute_mid() == 4

def test_cancel_sync(monkeypatch):
	blockchain = load_blockchain(monkeypatch)

	community = blockchain.BlockchainEngineeringCommunity.__new__(
		blockchain.BlockchainEngineeringCommunity
	)

	community.sync_block_buffer = [1]
	community.sync_block_count = 5
	community.sync_peer = object()
	community.sync_their_height = 100
	community.fork_height = 50
	community.mining_job_id = 0

	# Prevent a mining thread from starting
	community.start_pow_search_task = lambda: None

	blockchain.BlockchainEngineeringCommunity.cancel_sync(
		community
	)

	assert community.sync_block_buffer == []
	assert community.sync_block_count == 0
	assert community.sync_peer is None
	assert community.sync_their_height == 0
	assert community.fork_height == 0
	assert community.mining_job_id == 1