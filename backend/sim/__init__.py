"""Ranking-algorithm simulation harness (see docs/RANKING_SIMULATION.md).

Dev-only: not listed in [tool.setuptools].packages, so it never enters the
runtime image. `scenarios` is the single source of truth — `charts` plots its
output and tests/test_ranking_simulation.py asserts on the same output, so a
committed graph cannot drift from a passing test.
"""
