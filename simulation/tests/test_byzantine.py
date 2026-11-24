from wthraft import byzantine


def test_no_attackers_means_near_perfect_success():
    for protocol in byzantine.PROTOCOLS:
        assert byzantine.run_trial(protocol, 40, 0.0, 100, seed=1)["success"] >= 0.95, protocol


def test_raft_success_tracks_honest_leader_probability():
    runs = [byzantine.run_trial("Raft", 50, 0.2, 200, seed=s)["success"] for s in range(10)]
    assert 0.65 < sum(runs) / len(runs) < 0.9


def test_pbft_fails_beyond_one_third():
    assert byzantine.run_trial("PBFT", 50, 0.4, 50, seed=1)["success"] == 0.0
    assert byzantine.run_trial("PBFT", 50, 0.2, 50, seed=1)["success"] == 1.0


def test_wth_raft_penalises_and_suspends_persistent_liars():
    r = byzantine.run_trial("WTH-Raft", 50, 0.2, 100, seed=3)
    assert r["malicious_suspended"] == 10
    assert r["malicious_weight_share"] == 0.0
    assert r["success"] > 0.95


def test_sleepers_attack_only_in_the_second_half():
    r = byzantine.run_trial("WTH-Raft", 50, 0.2, 100, seed=3, strategy="sleeper")
    assert r["malicious_suspended"] == 10  # caught once they start lying


def test_weighting_beats_the_unweighted_ablation_at_30_percent():
    weighted = byzantine.success_rates(60, 0.3, rounds=100, trials=4)
    assert weighted["WTH-Raft"]["success"] > weighted["Two-hop (unweighted)"]["success"] + 0.2
