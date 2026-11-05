"""S9.1 — fovea scale benchmark (epic acceptance).

Validates the design's scalability claim (docs/ARCHITECTURE.md §3): at ~400k
nodes with average degree ~15, a foveal `stimulate` is a local update —
tens of light operations per event, hundreds of events/second on a modern CPU.

Run explicitly with:  pytest -m benchmark tests/test_benchmark.py
Skipped in normal runs (marker registered in conftest.py).
"""

from __future__ import annotations

import math
import statistics
import time

import pytest

from parthenos.fovea import FoveaEngine
from parthenos.node import MemoryNode, TypedEdge

NODES = 400_000
AVG_DEGREE = 15
EVENTS = 200

# Generous bounds (CI-safe): well above the design's claim of hundreds of
# events/s while leaving headroom for slow/virtualized hosts.
MIN_EVENTS_PER_SEC = 100.0
MAX_P99_MS = 20.0


def _build_graph(n: int, degree: int) -> dict[str, MemoryNode]:
    nodes: dict[str, MemoryNode] = {}
    for i in range(n):
        nodes[f"n{i}"] = MemoryNode(
            id=f"n{i}", created_at=0.0, last_recall=0.0, floatation=0.5
        )
    # Ring-with-vicinity edges: each node links to the next `degree` ids
    # (wrapping). Deterministic, out-degree exactly `degree` for all nodes.
    for i in range(n):
        node = nodes[f"n{i}"]
        node.edges = [
            TypedEdge(target_id=f"n{(i + k) % n}", kind="assoc")
            for k in range(1, degree + 1)
        ]
    return nodes


@pytest.mark.benchmark
def test_fovea_scale_400k_avg_degree_15():
    nodes = _build_graph(NODES, AVG_DEGREE)
    engine = FoveaEngine()  # beta=0.5, radius=3

    # Local-update volume: with radius 3 and degree 15, the foveal neighborhood
    # is far smaller than the graph (1 + 15 + 15² + 15³ ≈ 3616 max, but our BFS
    # touches ≤ 1 + degree + ... within radius). Assert it is not global.
    deltas = engine.stimulate(nodes["n0"], intensity=1.0, graph=nodes)
    assert len(deltas) <= 1 + AVG_DEGREE * (1 + AVG_DEGREE + AVG_DEGREE**2)
    assert len(deltas) < NODES // 100  # never near-global

    # Throughput: EVENTS random stimulates, wall-clock.
    sample = [f"n{math.floor(i * NODES / EVENTS) % NODES}" for i in range(EVENTS)]
    times: list[float] = []
    for i, nid in enumerate(sample):
        t0 = time.perf_counter()
        engine.stimulate(nodes[nid], intensity=0.5, graph=nodes)
        times.append(time.perf_counter() - t0)

    total = sum(times)
    events_per_sec = EVENTS / total if total > 0 else float("inf")
    p99 = statistics.quantiles(times, n=100)[98] * 1_000  # ms

    assert events_per_sec >= MIN_EVENTS_PER_SEC, (
        f"throughput {events_per_sec:.1f} events/s < {MIN_EVENTS_PER_SEC}"
    )
    assert p99 <= MAX_P99_MS, f"p99 {p99:.2f} ms > {MAX_P99_MS} ms"
    print(f"\n[fovea 400k] {events_per_sec:.0f} events/s  p99={p99:.2f} ms  "
          f"touched={len(deltas)} nodes")
