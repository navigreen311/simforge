"""15 rubric dimension scorers (blueprint §C.10).

v1 uses deterministic heuristics over the transcript + CCB pre/post diff + scenario
metadata (offline, reproducible). The LLM-judge dimensions (P7 CX, C1, C2) swap to real
model calls behind these same function signatures later.
"""
