"""Round-based simulation of consensus correctness with malicious (Byzantine) nodes.

Each round the network decides whether a submitted quality record is valid.
Honest nodes vote correctly, except for a small error rate. Malicious nodes
collude and vote for the wrong outcome, the paper's "falsified pesticide or
storage data". A round succeeds if the network's decision matches the truth.

Two attacker strategies:
- "always": malicious nodes lie every round. This is the easy case for a
  reputation system, which catches them within a couple of rounds.
- "sleeper": malicious nodes behave honestly for the first half of the run,
  building up reputation (and becoming primaries), then all lie at once. This
  is the harder case for WTH-Raft.

Protocols:
- Raft: the leader (re-elected at random every `term` rounds) decides, and
  followers replicate its entry. Raft assumes no Byzantine nodes, so a
  malicious leader's entry is committed.
- PBFT: a value is decided when at least 2f+1 replicas vote for it
  (f = floor((n-1)/3)). Otherwise no decision is reached, which counts as a
  failure.
- Two-hop (unweighted): an ablation, not from the paper. It uses WTH-Raft's
  two-hop structure with one node, one vote. Primaries are picked at random each
  term. A malicious primary reports its whole cluster as voting for the wrong
  outcome.
- WTH-Raft: the same structure, but the leader and primaries are the
  highest-weight eligible nodes, re-chosen every round, and votes are weighted
  by W = (alpha*Q + beta*R)/100. After each round the off-chain inspection
  reveals the truth, and every node's report goes through the contract's rules
  (reputation.record_inspection): honest reports earn +2, inconsistent ones
  cost 20, and an R-Score below 20 suspends the node (weight 0, no vote, never a
  primary).
"""
import math
import random

from .reputation import Supplier, record_inspection, weight


def _votes(n, malicious, truth, honest_error, rng, attacking=True):
    def honest_vote():
        return truth if rng.random() >= honest_error else not truth
    return [(not truth) if (i in malicious and attacking) else honest_vote() for i in range(n)]


def _clusters(ordered_nodes, k):
    leader, primaries, rest = ordered_nodes[0], ordered_nodes[1:k + 1], ordered_nodes[k + 1:]
    clusters = {p: [p] for p in primaries}
    for i, node in enumerate(rest):
        clusters[primaries[i % len(primaries)]].append(node)
    return leader, clusters


def run_trial(protocol, n, malicious_fraction, rounds, seed, honest_error=0.01, term=10, strategy="always"):
    rng = random.Random(f"{protocol}-{n}-{malicious_fraction}-{seed}-{strategy}")
    attack_from = rounds // 2 if strategy == "sleeper" else 0
    malicious = set(rng.sample(range(n), round(malicious_fraction * n)))
    product_quality = [rng.randint(60, 95) for _ in range(n)]  # what inspections find, per node
    suppliers = [Supplier() for _ in range(n)]
    k = max(1, round(math.sqrt(n - 1)))
    f = (n - 1) // 3

    successes = []
    leader = None
    groups = None
    for round_no in range(rounds):
        truth = rng.random() < 0.5
        attacking = round_no >= attack_from
        votes = _votes(n, malicious, truth, honest_error, rng, attacking)

        if protocol == "Raft":
            if round_no % term == 0:
                leader = rng.randrange(n)
            decision = votes[leader]

        elif protocol == "PBFT":
            for_truth = sum(1 for v in votes if v == truth)
            decision = truth if for_truth >= 2 * f + 1 else (not truth if n - for_truth >= 2 * f + 1 else None)

        elif protocol == "Two-hop (unweighted)":
            if round_no % term == 0:
                order = list(range(n))
                rng.shuffle(order)
                _, groups = _clusters(order, k)
            tally = 0
            for primary, members in groups.items():
                if primary in malicious:
                    tally -= len(members)            # reports the whole cluster for the wrong outcome
                    continue
                tally += sum(1 if votes[m] == truth else -1 for m in members)
            decision = truth if tally > 0 else not truth

        elif protocol == "WTH-Raft":
            eligible = [i for i in range(n) if not suppliers[i].suspended]
            eligible.sort(key=lambda i: (-weight(suppliers[i]), i))
            _, clusters = _clusters(eligible, min(k, max(1, len(eligible) - 1)))
            tally = 0
            for primary, members in clusters.items():
                cluster_weight = sum(weight(suppliers[m]) for m in members)
                if primary in malicious:
                    tally -= cluster_weight
                    continue
                tally += sum(weight(suppliers[m]) * (1 if votes[m] == truth else -1) for m in members)
            decision = truth if tally > 0 else not truth
            # Off-chain inspection reveals the truth; the contract scores every report.
            for i in eligible:
                record_inspection(suppliers[i], votes[i] == truth, product_quality[i])

        else:
            raise ValueError(protocol)

        successes.append((decision == truth, attacking))

    honest = [i for i in range(n) if i not in malicious]
    total_weight = sum(weight(s) for s in suppliers) or 1
    attack_rounds = [ok for ok, attacking in successes if attacking]
    return {
        "success": sum(ok for ok, _ in successes) / rounds,
        "success_during_attack": sum(attack_rounds) / max(1, len(attack_rounds)),
        "success_first_10_attack_rounds": sum(attack_rounds[:10]) / max(1, len(attack_rounds[:10])),
        "malicious_weight_share": sum(weight(suppliers[i]) for i in malicious) / total_weight,
        "honest_suspended": sum(1 for i in honest if suppliers[i].suspended),
        "malicious_suspended": sum(1 for i in malicious if suppliers[i].suspended),
    }


PROTOCOLS = ["Raft", "PBFT", "Two-hop (unweighted)", "WTH-Raft"]


def success_rates(n, malicious_fraction, rounds=200, trials=20, strategy="always"):
    results = {}
    for protocol in PROTOCOLS:
        runs = [run_trial(protocol, n, malicious_fraction, rounds, seed, strategy=strategy) for seed in range(trials)]
        results[protocol] = {key: sum(r[key] for r in runs) / trials for key in runs[0]}
    return results
