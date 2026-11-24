"""Message-level simulation of consensus latency and throughput.

Model (the same for every protocol, so the comparison is fair):
- Each node has one CPU. Sending a message costs it `cpu_ms` of CPU time, and
  so does processing a received message. A node does one thing at a time:
  broadcasts are serialised, and received messages queue.
- Each message also takes a network delay, drawn from a log-normal
  distribution with mean `delay_ms`.
- Latency: time from the leader starting a transaction to the commit point
  (Raft: leader has a majority of acks; PBFT: f+1 replicas committed, enough
  for a client to accept; WTH-Raft: leader has aggregates covering a majority).
- Throughput: with transactions pipelined, the busiest node's CPU time per
  transaction is the bottleneck, so TPS = 1000 / max(node CPU ms per tx).

Not modelled: bandwidth limits, batching, disk writes, view changes or
elections, and signature aggregation. These are simplifications. They leave
the comparison about message patterns, which is what the two-hop design
changes.
"""
import heapq
import math
import random


class Network:
    def __init__(self, n, cpu_ms, delay_ms, jitter, rng):
        self.n = n
        self.cpu_ms = cpu_ms
        self.mu = math.log(delay_ms) - jitter ** 2 / 2  # log-normal with the given mean
        self.sigma = jitter
        self.rng = rng
        self.busy_until = [0.0] * n
        self.work = [0.0] * n
        self.queue = []
        self.seq = 0
        self.messages = 0

    def _cpu(self, node, ready_at):
        start = max(ready_at, self.busy_until[node])
        self.busy_until[node] = start + self.cpu_ms
        self.work[node] += self.cpu_ms
        return start + self.cpu_ms

    def send(self, src, dst, at, kind):
        sent = self._cpu(src, at)
        arrive = sent + self.rng.lognormvariate(self.mu, self.sigma)
        self.seq += 1
        self.messages += 1
        heapq.heappush(self.queue, (arrive, self.seq, dst, src, kind))
        return sent

    def broadcast(self, src, dsts, at, kind):
        t = at
        for dst in dsts:
            t = self.send(src, dst, t, kind)
        return t

    def run(self, handler):
        while self.queue:
            arrive, _, dst, src, kind = heapq.heappop(self.queue)
            done = self._cpu(dst, arrive)
            handler(dst, src, kind, done)


def raft(n, net):
    majority = n // 2 + 1
    state = {"acks": 1, "commit": None}  # the leader counts itself

    def handle(node, src, kind, t):
        if kind == "append":
            net.send(node, 0, t, "ack")
        elif kind == "ack":
            state["acks"] += 1
            if state["commit"] is None and state["acks"] >= majority:
                state["commit"] = t

    net.broadcast(0, range(1, n), 0.0, "append")
    net.run(handle)
    return state["commit"]


def pbft(n, net):
    f = (n - 1) // 3
    others = {i: [j for j in range(n) if j != i] for i in range(n)}
    prepares = [0] * n
    commits = [0] * n
    has_preprepare = [False] * n
    sent_commit = [False] * n
    committed_at = []

    def maybe_commit(node, t):
        # Prepared: the pre-prepare plus 2f matching prepares from others.
        if not sent_commit[node] and has_preprepare[node] and prepares[node] >= 2 * f:
            sent_commit[node] = True
            commits[node] += 1  # its own commit
            net.broadcast(node, others[node], t, "commit")

    def handle(node, src, kind, t):
        if kind == "preprepare":
            has_preprepare[node] = True
            net.broadcast(node, others[node], t, "prepare")
            maybe_commit(node, t)
        elif kind == "prepare":
            prepares[node] += 1
            maybe_commit(node, t)
        elif kind == "commit":
            commits[node] += 1
            if commits[node] == 2 * f + 1:
                committed_at.append(t)

    has_preprepare[0] = True
    net.broadcast(0, others[0], 0.0, "preprepare")
    net.run(handle)
    committed_at.sort()
    return committed_at[f] if len(committed_at) > f else None  # f+1 replicas committed


def two_hop_groups(n):
    """Leader 0; primaries 1..k with k = round(sqrt(n-1)); the rest split round-robin among them."""
    k = max(1, round(math.sqrt(n - 1)))
    primaries = list(range(1, k + 1))
    clusters = {p: [] for p in primaries}
    for i, node in enumerate(range(k + 1, n)):
        clusters[primaries[i % k]].append(node)
    return primaries, clusters


def wth_raft(n, net):
    primaries, clusters = two_hop_groups(n)
    primary_of = {m: p for p, members in clusters.items() for m in members}
    majority = n // 2 + 1
    state = {"covered": 1, "commit": None}  # leader counts itself
    acks = {p: 1 for p in primaries}        # each primary counts itself
    reported = set()

    def handle(node, src, kind, t):
        if kind == "propose" and node in clusters:          # primary: forward to its cluster
            net.broadcast(node, clusters[node], t, "forward")
            if not clusters[node] and node not in reported:
                reported.add(node)
                net.send(node, 0, t, "aggregate")
        elif kind == "forward":                              # member: ack its primary
            net.send(node, primary_of[node], t, "ack")
        elif kind == "ack":                                  # primary: aggregate once a cluster majority acked
            acks[node] += 1
            if node not in reported and acks[node] >= (len(clusters[node]) + 1) // 2 + 1:
                reported.add(node)
                net.send(node, 0, t, "aggregate")
        elif kind == "aggregate":                            # leader: commit once a node majority is covered
            state["covered"] += len(clusters[src]) + 1
            if state["commit"] is None and state["covered"] >= majority:
                state["commit"] = t

    net.broadcast(0, primaries, 0.0, "propose")
    net.run(handle)
    return state["commit"]


PROTOCOLS = {"Raft": raft, "PBFT": pbft, "WTH-Raft": wth_raft}


def measure(protocol, n, samples, cpu_ms=0.2, delay_ms=5.0, jitter=0.25, seed=0):
    """Mean latency (ms), throughput (tx/s) and messages per transaction."""
    rng = random.Random(f"{protocol}-{n}-{seed}")
    latencies, bottlenecks, messages = [], [], []
    for _ in range(samples):
        net = Network(n, cpu_ms, delay_ms, jitter, rng)
        latency = PROTOCOLS[protocol](n, net)
        latencies.append(latency)
        bottlenecks.append(max(net.work))
        messages.append(net.messages)
    return {
        "latency_ms": sum(latencies) / samples,
        "tps": 1000.0 / (sum(bottlenecks) / samples),
        "messages": sum(messages) / samples,
    }
