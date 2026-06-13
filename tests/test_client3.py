from types import SimpleNamespace


def test_on_peer_added_tracks_server_and_peer(monkeypatch):
	monkeypatch.setenv("CLIENT_3_COMMUNITY_ID", "00" * 32)
	monkeypatch.setenv("GROUP_ID", "1")
	monkeypatch.setenv("MY_ORDER", "1")
	monkeypatch.setenv("KEYS_FILE", "/tmp/dummy-keys")
	monkeypatch.setattr("asyncio.run", lambda coro: None)

	import client_3_blockchain as blockchain

	community = blockchain.BlockchainEngineeringCommunity.__new__(blockchain.BlockchainEngineeringCommunity)
	community.server = None
	community.peers = {}

	server_peer = SimpleNamespace(
		public_key=SimpleNamespace(key_to_bin=lambda: blockchain.SERVER_PUBLIC_KEY),
		address=("127.0.0.1", 1234),
	)
	other_key = next(iter(blockchain.OTHER_PEER_KEYS))
	other_peer = SimpleNamespace(
		public_key=SimpleNamespace(key_to_bin=lambda: other_key),
		address=("127.0.0.1", 4321),
	)

	blockchain.BlockchainEngineeringCommunity.on_peer_added(community, server_peer)
	blockchain.BlockchainEngineeringCommunity.on_peer_added(community, other_peer)

	assert community.server is server_peer
	assert community.peers[other_key] is other_peer
