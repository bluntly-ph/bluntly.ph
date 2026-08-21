"""Browser assertions must retry, because the page is still arriving.

Next's App Router streams: `page.goto()` resolves on `load` and content keeps
filling in afterwards. Any assertion that reads the DOM *once* races that
stream, and the result is not a failure but a flake — which is worse, because
a gate that fails one run in three teaches everyone to re-run it, and then it
stops being read at all.

Three of these were found, all in specs written to catch real problems:

  * `console-health` waited for `networkidle`, which a Next app never reaches
    (the router prefetches, Chrome deprioritises, the requests just sit there).
    Five of seven tests failed against production on a site whose load event
    fires in 564ms with zero console errors.
  * `console-health` read `body.innerText` once and saw 15 characters on one
    run in three, and 1874 on the others.
  * `responsive` used `expect(await locator.count())`, which is a snapshot, and
    failed roughly one run in three.

`expect(locator)` retries. `expect(await locator.someQuery())` does not — the
`await` resolves before `expect` ever sees it. That is the whole distinction,
and it is invisible at a glance, which is why this is a test rather than a
convention.

Lives in the Python suite because that is the suite that runs here; the repo
has no JavaScript test runner.
"""

from __future__ import annotations

import pathlib
import re

import pytest

E2E = pathlib.Path(__file__).resolve().parents[2] / "e2e"

#: `expect(await <locator>.count())` and friends: resolved before expect sees
#: them, so Playwright cannot retry.
SNAPSHOT_ASSERT = re.compile(
    r"expect\(\s*await\s+[\w.]+\.(count|innerText|textContent|inputValue|"
    r"allTextContents|isVisible|isEnabled)\(", re.M)

#: Discouraged by Playwright's own docs, and never reached by a Next app.
NETWORK_IDLE = re.compile(r"waitUntil:\s*[\"']networkidle[\"']")

SPECS = sorted(E2E.glob("*.spec.ts")) if E2E.exists() else []


def code_only(source: str) -> str:
    """Blank out comments, keeping line numbers.

    The first version of this check flagged the comment that *explains* the
    rule, which would have meant nobody could document it without tripping it.
    """
    out = []
    in_block = False
    for line in source.splitlines():
        stripped = line.strip()
        if in_block:
            out.append("")
            if "*/" in line:
                in_block = False
            continue
        if stripped.startswith("/*"):
            out.append("")
            if "*/" not in line:
                in_block = True
            continue
        if stripped.startswith("//"):
            out.append("")
            continue
        out.append(line.split("//")[0] if "//" in line else line)
    return chr(10).join(out)


@pytest.mark.skipif(not SPECS, reason="e2e specs not checked out")
@pytest.mark.parametrize("spec", SPECS, ids=lambda p: p.name)
def test_no_snapshot_assertions(spec):
    source = code_only(spec.read_text(encoding="utf-8"))
    hits = [
        f"line {source[:m.start()].count(chr(10)) + 1}: {m.group(0)}"
        for m in SNAPSHOT_ASSERT.finditer(source)
    ]
    assert not hits, (
        f"{spec.name} asserts on a resolved value, so Playwright cannot retry "
        f"it and it will flake against a streaming page:\n  " + "\n  ".join(hits)
        + "\nUse expect(locator).toHaveCount(...) / .toBeVisible() instead."
    )


@pytest.mark.skipif(not SPECS, reason="e2e specs not checked out")
@pytest.mark.parametrize("spec", SPECS, ids=lambda p: p.name)
def test_no_networkidle_waits(spec):
    source = code_only(spec.read_text(encoding="utf-8"))
    hits = [
        f"line {source[:m.start()].count(chr(10)) + 1}"
        for m in NETWORK_IDLE.finditer(source)
    ]
    assert not hits, (
        f"{spec.name} waits for networkidle at {hits}. Next's router prefetches "
        f"the destinations of visible links and Chrome leaves those requests "
        f"pending, so the network never goes idle and the test times out "
        f"having asserted nothing."
    )


@pytest.mark.skipif(not SPECS, reason="e2e specs not checked out")
def test_there_are_specs_to_check():
    """If the glob stops matching, both checks above pass on nothing."""
    assert len(SPECS) >= 5, f"only found {len(SPECS)} specs in {E2E}"
