# A verifier that transfers — and catches the fixes everyone trusts

> Aegis, Act II. The verifier was proven to be a *verifier*, not a path-traversal checker:
> it judged a second, unrelated vulnerability family with **zero changes to its core** — and
> in doing so it flagged two of the most widely-recommended security fixes as incomplete.

## The one-sentence result

A vulnerability-agnostic verifier core — the part that scores patches, abstains when it can't
judge, and reports its own coverage — ran a **path-traversal** gold set and a **command-injection**
gold set through *identical code*. Adding the second vulnerability family was a single new plugin
file; the diff to the core was empty. That empty diff is the whole claim: the measurement layer
generalizes across vulnerability classes instead of being rebuilt per bug.

## The findings a reader should remember

Two patches that look like the textbook "correct" answer were exposed as only *partially* correct —
each defends one shape of the attack and silently leaks another:

- **`normpath` (path traversal).** A patch that normalizes the path and rejects `../` and absolute
  paths — the canonical fix — was judged genuine for the entire project, until the verifier tested a
  *symlink* whose filename was perfectly innocent. `normpath` is string manipulation; it cannot see
  that a directory in the path is a symlink pointing outside the allowed folder. It fell.
- **`shlex.quote` (command injection).** The fix every developer is taught for shell injection. It
  escapes shell metacharacters (`;`, `|`, `$()`), so it blocks command injection — but it passes an
  input like `--output=/etc/cron.d/evil` straight through as a **command-line flag**. Quoting a flag
  doesn't stop it from being a flag. The verifier caught it; so did `subprocess` list-form, the *other*
  textbook fix, for the same reason.

Both are the same lesson in two domains: a defense that is correct against the *obvious* shape of an
attack can be blind to a related shape within the same vulnerability family. A pass/fail benchmark that
only tests the obvious shape certifies these patches as real — forever. A verifier that tests the
family catches them.

## What "transfer" actually means here

The core knows nothing about paths, shells, or files. A vulnerability enters only as a **plugin** that
supplies four things: a behavioral oracle (did the attack actually succeed?), a battery of exploits, a
registry of candidate patches, and a class taxonomy. The core does the rest — runs held-out and fuzzed
exploits against each patch, checks that legitimate inputs still work, assigns genuine / gamed / abstain,
and measures its own precision and recall against the gold set.

Path traversal's oracle is *path containment* ("did the written file resolve to outside the upload
directory?"). Command injection's oracle is a *benign side-effect* ("did an injected sentinel command
actually execute?"). Completely different mechanisms — and the same scoring, abstention, and
coverage-reporting core consumed both without modification. Vuln-specific knowledge lives in the plugin;
verifier *logic* never does. That separation is what makes it generalize rather than overfit.

## It knows when it can't judge

The verifier does not always answer. Before it blesses a patch as genuine, it checks whether its own
attack suite actually covers the vulnerability's known attack classes. If it doesn't, it returns
**ABSTAIN** with the reason — "I haven't tested this geometry, so I won't certify it" — instead of a
confident-but-hollow "genuine." This abstention is gated on an objective coverage check, never a tunable
confidence knob (a knob would let the verifier dodge hard cases to flatter its own accuracy).

Crucially, the abstention is *honest deferral*, not error-hiding — and that was proven, not assumed. On
path traversal, the verifier abstained on a set of patches it couldn't yet judge; when the missing
attack coverage was later added, every one of those deferred patches resolved to the *correct* verdict,
with zero false positives or negatives. It had been waiting for coverage it didn't have, not hiding
mistakes.

The same machinery applied the lesson *forward*: when adding command injection, the argument-injection
geometry was declared and tested from the start — which is why `shlex.quote`'s failure was a *predicted*
result rather than a surprise discovered three rounds later.

## Honest limits — the contribution is knowing them

Everything above runs on **synthetic, hand-authored gold sets**. That makes the precision/recall numbers
internally clean (100% on what it grades, across both families) but they are measured against labels the
author defined — so the next real test is whether the verifier holds on *real* patches for *real* CVEs,
where the genuine/gamed line is far messier. Two narrower limits are also on the record: the
argument-injection oracle is currently a string-property proxy rather than a true behavioral one, and the
sanitizer-function model can't yet represent fixes that change the *call pattern* (e.g. switching to a
no-shell API) rather than the input.

None of these undercut the transfer result; they scope it. The verifier is a *characterized
approximation* — it reports what it tested, abstains on what it didn't, and never claims completeness it
can't back. The point of the project is not a verifier that is always right. It is a verifier whose
reliability, and whose blind spots, come with numbers — the thing security-agent benchmarks still don't
measure.

---

*Builds on [act2-verifier.md](act2-verifier.md) (how the verifier and its "verify the verifier"
precision/recall discipline were constructed). Next: take the machinery to a real BountyBench CVE and
report against published baselines.*
