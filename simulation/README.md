# WTH-Raft simulation

This simulation tests the paper's performance and security claims for the Weighted Two-Hop Raft (WTH-Raft) consensus. It compares WTH-Raft with standard Raft and PBFT.

**Results:** [results/RESULTS.md](results/RESULTS.md) has the tables and charts, and checks each of the paper's claims against the numbers.

```bash
pip install -r simulation/requirements.txt    # matplotlib, for the charts
python simulation/run.py                      # full run, a few seconds; rewrites simulation/results/
python -m pytest simulation/tests             # tests
```

The run is deterministic: the same code always produces the same numbers. CI runs the tests and a `--quick` run on every change.

## What is from the paper, and what is not

The paper describes the ideas, but gives few numbers. Where it is silent, the choice below is this implementation's, and is marked *(choice)*.

| Element | Source |
| --- | --- |
| Two-tier structure: leader, primaries (group leaders), clusters | Paper |
| Weight per node from Q-Score and R-Score, W = αQ + βR | Paper (written there as R = αQ + βS) |
| Penalties for inconsistent quality reports; suspending repeat offenders | Paper |
| Comparison with Raft and PBFT on latency, TPS and Byzantine resilience | Paper |
| α = β = 0.5; reward +2; penalty −20; tolerance 10; suspension below R = 20; Q as a moving average | *(choice)*, the contract's defaults ([TraceabilityManagement.sol](../AgricultureFoodSupplyChain-Truffle/contracts/TraceabilityManagement.sol)) |
| Number of primaries k = round(√(n−1)); clusters assigned round-robin | *(choice)* |
| Network: 0.2 ms CPU per message, 5 ms mean one-way delay (log-normal) | *(choice)* |
| Unweighted two-hop protocol | *(choice)*: an ablation that isolates the effect of the weighting |
| Sleeper attackers | *(choice)*: a harder attack than the paper's |

The reputation rules in [wthraft/reputation.py](wthraft/reputation.py) mirror the contract exactly. A test checks the constants against the Solidity source.

## Performance model ([wthraft/network.py](wthraft/network.py))

This is a discrete-event simulation at the message level:

- **CPU:** every node has one CPU. Sending or processing a message costs it 0.2 ms, and a broadcast is a sequence of sends.
- **Network:** every message also takes a log-normal network delay, averaging 5 ms.
- **Latency:** the time from the leader starting a transaction to its commit point.
  - Raft: a majority of acks.
  - PBFT: f+1 replicas have committed.
  - WTH-Raft: the leader holds aggregates covering a majority of nodes. Each primary reports once a majority of its cluster has acked.
- **Throughput:** with transactions pipelined, the busiest node's CPU time per transaction limits TPS.

**Not modelled:**
- bandwidth limits
- batching
- disk writes
- leader elections and view changes
- signature aggregation

These are simplifications. They keep the comparison about what two-hop actually changes: who sends which messages.

## Byzantine model ([wthraft/byzantine.py](wthraft/byzantine.py))

Each round, the network decides whether a quality record is valid:

- **Honest nodes** vote correctly, except for a 1% error rate.
- **Malicious nodes** collude to vote wrongly.
- **Malicious primaries** report their whole cluster as voting wrongly.

The protocols decide differently:

- **Raft:** the leader decides.
- **PBFT:** needs 2f+1 matching votes.
- **WTH-Raft:** a weighted vote. Leader and primaries are the highest-weight eligible nodes, re-chosen every round. After each round, every report is scored by the contract's rules.

The **key assumption** is that after every round an off-chain inspection reveals the truth. In other words, the reputation engine has a reliable oracle. Real inspections are slower, sampled and fallible. With a weaker oracle, malicious nodes keep their weight for longer, and WTH-Raft's results move towards the unweighted two-hop line.
