# Validated on a real CVE — the verifier catches a fix the test suite accepts

> Aegis, Act III (bridge). The verifier left the synthetic gold sets and judged a real,
> disclosed CVE on a real Dockerized service — and caught a plausible patch that passes the
> project's *entire* functional test suite while leaving the vulnerability open.

## The one-sentence result

Against **MLflow CVE-2024-1558** (a path-traversal flaw), running as a real MLflow server in
Docker with real exploit traffic and real flag exfiltration, the verifier graded four patches
correctly: the official fix as **genuine**, and three broken fixes as **gamed** — including one
that passes **all 148 of MLflow's own functional tests.** The verifier core was not modified to do
this; the entire real-CVE harness is a plugin (the third vulnerability type to run with an empty
core diff).

## The finding a reader should remember

`x_partial_decode` is a patch a competent engineer would plausibly write and a reviewer would
plausibly accept: *URL-decode the input, then reject any `..` in the path.* It looks like a
methodical, defense-in-depth fix. It **passes every functional test** — MLflow's server (85/85),
data (11/11), and store (52/52) suites all green. By the standard that real-world patch
verification actually uses — *did the tests pass?* — it ships.

It is still exploitable. `urlparse()` silently strips the `#`-fragment before returning `.path`,
so a traversal hidden after a `%23` is invisible to the check — and the verifier, firing the
exploit at the patched server, watches the flag get read off the filesystem anyway. **Test-suite
verification accepts the patch; the verifier rejects it**, because it checks the behavior, not the
test result. That gap — a plausible, test-passing fix that doesn't close the vector — is the entire
reason the project exists, now shown on a real bug rather than a synthetic one.

## Three patches, three detection mechanisms

The run exercised all three ways a patch can fail, each caught by a different part of the verifier:

- `x_strip` and `x_partial_decode` — **exploit-leaking**: pass the functional tests, but a held-out
  exploit still fires. Caught by the behavioral oracle.
- `x_delete_feature` — **functionality-breaking**: blocks every exploit, but "fixes" the bug by
  refusing legitimate inputs (one server test drops, 84/85). Caught by the functionality gate.
- `official` — **genuine**: blocks the held-out exploits *and* keeps all 148 tests green. Confirmed,
  not assumed.

Result on the four: precision 100%, recall 100%, F1 100%, zero abstention — on a real CVE, with the
oracle reading an exfiltrated flag out of a live container, not a synthetic file check.

## It abstained before it was right — and that was the point

The first run did *not* score the official patch as genuine. It returned **ABSTAIN**. The verifier's
held-out attack set covered a variant of the traversal but not the actual `%23` fragment-anchor
mechanism that defines this CVE — so it refused to certify a fix it had not independently attacked
with the real bug's mechanism. On the single most important patch, it flagged that *our own test set
was inadequate to judge it* rather than rubber-stamping. Adding one held-out exploit in the real
attack class resolved the official patch to genuine and abstention to zero. The calibration layer
worked exactly as designed: honest deferral first, confident verdict only once the coverage existed
to back it.

## Transferability held at the real boundary

The synthetic plugins ran in-process; this one drives an HTTP exploit at a Dockerized server,
applies a 79KB patched file into a running container, restarts it, and reads a flag via
`docker exec`. None of that touched the core: `git diff` on `core.py` and `plugin.py` is empty. The
same three-way scoring, abstention, and coverage logic that ran synthetic path-traversal and
command-injection ran a live CVE without modification. Transferability is a property of the
architecture, not a one-off — now demonstrated across three vulnerability types and the
synthetic→real jump.

## Independent ground truth — a real fix, caught

The MLflow gamed patches above are self-authored — *expert-plausible*, but ours. To remove the "you
wrote the fake" objection entirely, a scan of the benchmark turned up a real one: **LibreChat**, where
a shipped fix for a path-traversal CVE (CVE-2024-10361, the file-*delete* endpoint) left the *same
vulnerability class* open in a sibling handler (CVE-2024-11170, the file-*upload* endpoint) — two
separately disclosed CVEs against the same version, the textbook "fixed one site, missed its sibling"
incomplete fix.

Built as a second real-CVE plugin — again with **zero core changes** — the verifier judged that real
shipped fix (`x_b0_crud`, the maintainer's actual `crud.js` patch) for the upload vulnerability. It is
a *genuine* security improvement (it correctly closes the delete-path CVE and passes LibreChat's
functional tests), yet the verifier labels it **GAMED**: the held-out upload exploit still fires, so
the traversal class is not closed — and a second real CVE is the independent proof it was incomplete.
Verdicts were stable across N=3 trials (precision/recall/F1 100%, zero abstention) on a sound oracle —
a per-run UUID sentinel watched via a kernel filesystem event, with the watch established before the
exploit fires so a fast write can't be missed.

This is the strongest form of the result: **a real, shipped, test-passing fix — caught as incomplete
by the verifier, and confirmed incomplete by a separate CVE — not a fake we constructed.** And it is
the fourth vulnerability type (after synthetic traversal, synthetic command-injection, and the MLflow
real CVE) to run through the same core untouched.

## Honest limits — stated, not hidden

The MLflow gamed patches are self-authored — *expert-plausible* (a reviewer would accept
`x_partial_decode`), which is what makes that demo credible, but still ours. The LibreChat result
above removes the objection entirely with a real maintainer-shipped incomplete fix. On coverage, the
LibreChat held-out set was widened to a family of percent-encoding variants plus a grammar fuzzer
(~50 inputs), and the official `path.basename` fix held against all of them at N=3 — its robustness is
across the *encoding family*, not a single payload. The honest residuals, stated rather than hidden:
a *mutation* fuzzer at MLflow's scale (~8k inputs) is impractical here because the live HTTP oracle
runs orders of magnitude slower than MLflow's in-process check — a genuine throughput tradeoff of
live-target verification, not a missing capability; symlink-to-file and multi-endpoint coverage are
different *geometries* left for later; and the oracle confirms the traversal *created a file* (a kernel
CREATE event on a unique sentinel), not its *contents*. None of these is a correctness gap for the
result shown — the caught fix leaks plain `../`, which the suite covers. (A bonus from the fuzzing:
overlong-UTF-8 and null-byte inputs *crash* the container — a denial-of-service finding, distinct from
traversal and excluded from this gold set.)

Two precision notes, in the project's own spirit. The claim is that the verifier beats
**test-suite-based acceptance** (the real-world default), demonstrated by `x_partial_decode` passing
all 148 functional tests while the verifier catches it — not that it beats a benchmark's full
exploit-recheck. And the sample is small (four patches): this is a *validation that the machinery
judges a real CVE correctly*, not a statistical measurement. The bar itself is thin — no published
system does exploit-based patch verification with measured precision and calibrated abstention, so
"at bar" means the bar this work defines.

---

*Builds on [act2-verifier.md](act2-verifier.md) (how the verifier was constructed) and
[act2-transferability.md](act2-transferability.md) (vuln-agnostic core, zero core changes). Next: the
agent — the half that generates exploits and patches for the now-validated verifier to score against
published BountyBench baselines.*
