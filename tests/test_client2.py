from types import SimpleNamespace
import importlib


def load_client(monkeypatch):
    monkeypatch.setenv("GROUP_ID", "test-group")
    monkeypatch.setenv("MY_ORDER", "1")
    monkeypatch.setenv("KEYS_FILE", "/tmp/dummy-key")

    monkeypatch.setattr("asyncio.run", lambda coro: None)

    import client_2
    importlib.reload(client_2)

    return client_2


# READY STATE

def test_mark_ready(monkeypatch):
    client = load_client(monkeypatch)

    community = client.BlockchainEngineeringCommunity.__new__(
        client.BlockchainEngineeringCommunity
    )

    community.ready = [False, False, False]

    community.mark_ready(client.PUBLIC_KEY_2)

    assert community.ready == [False, True, False]


def test_all_ready_true(monkeypatch):
    client = load_client(monkeypatch)

    community = client.BlockchainEngineeringCommunity.__new__(
        client.BlockchainEngineeringCommunity
    )

    community.ready = [True, True, True]

    assert community.all_ready()


def test_all_ready_false(monkeypatch):
    client = load_client(monkeypatch)

    community = client.BlockchainEngineeringCommunity.__new__(
        client.BlockchainEngineeringCommunity
    )

    community.ready = [True, False, True]

    assert not community.all_ready()


# COMPUTATION

def test_send_to_others_skips_self(monkeypatch):
    client = load_client(monkeypatch)

    community = client.BlockchainEngineeringCommunity.__new__(
        client.BlockchainEngineeringCommunity
    )

    me = object()
    peer2 = object()
    peer3 = object()

    community.my_peer = me
    community.peers = [me, peer2, peer3]

    sent = []

    community.ez_send = lambda peer, payload: sent.append(peer)

    community.send_to_others(client.ReadyMessage(True))

    assert sent == [peer2, peer3]

# BUNDLE SUBMISSION

def test_maybe_submit_bundle_not_ready(monkeypatch):
    client = load_client(monkeypatch)

    community = client.BlockchainEngineeringCommunity.__new__(
        client.BlockchainEngineeringCommunity
    )

    community.round_number = 1
    community.submitted_rounds = set()

    community.sigs = [
        b"a",
        None,
        b"c",
    ]

    called = []

    community.ez_send = lambda *args: called.append(True)

    community.server = object()

    community.maybe_submit_bundle()

    assert called == []


def test_maybe_submit_bundle_ready(monkeypatch):
    client = load_client(monkeypatch)

    community = client.BlockchainEngineeringCommunity.__new__(
        client.BlockchainEngineeringCommunity
    )

    community.round_number = 1
    community.submitted_rounds = set()

    community.sigs = [
        b"a",
        b"b",
        b"c",
    ]

    community.server = object()

    called = []

    community.ez_send = (
        lambda peer, payload: called.append(payload)
    )

    community.maybe_submit_bundle()

    assert len(called) == 1
    assert 1 in community.submitted_rounds