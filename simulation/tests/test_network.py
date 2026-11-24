import pytest

from wthraft import network


@pytest.mark.parametrize("n", [4, 10, 25])
def test_message_counts(n):
    assert network.measure("Raft", n, 1)["messages"] == 2 * (n - 1)
    assert network.measure("WTH-Raft", n, 1)["messages"] == 2 * (n - 1)
    # pre-prepare + prepares from every backup + commits from every replica
    assert network.measure("PBFT", n, 1)["messages"] == (n - 1) + (n - 1) ** 2 + n * (n - 1)


@pytest.mark.parametrize("n", [5, 10, 26, 101])
def test_two_hop_groups_cover_every_node_once(n):
    primaries, clusters = network.two_hop_groups(n)
    members = [m for ms in clusters.values() for m in ms]
    assert sorted([0] + primaries + members) == list(range(n))


def test_every_protocol_commits():
    for protocol in network.PROTOCOLS:
        assert network.measure(protocol, 16, 2)["latency_ms"] > 0


def test_two_hop_trades_latency_at_small_scale_for_scale():
    assert network.measure("WTH-Raft", 10, 10)["latency_ms"] > network.measure("Raft", 10, 10)["latency_ms"]
    assert network.measure("WTH-Raft", 150, 10)["latency_ms"] < network.measure("Raft", 150, 10)["latency_ms"]
    assert network.measure("WTH-Raft", 100, 5)["tps"] > network.measure("Raft", 100, 5)["tps"]


def test_runs_are_deterministic():
    assert network.measure("PBFT", 20, 3, seed=7) == network.measure("PBFT", 20, 3, seed=7)
