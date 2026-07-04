# Changelog

## 2.4.0

- **Added certified-schema learning** (`--learn PATH`, requires `--bnm`, and `--use-lemmas PATH`):
  - `--learn` computes the depth flip gain, generalizes it by resolution on complementary
    bivalent body literals, certifies each candidate classically against the
    totality-extended program (UNSAT probe over all groundings), and writes certified
    schemas as ab-guarded default lemmas (new module `klingo_learn.py`);
  - resolution iterates only through shrinking lemmas, so full case enumerations compile
    to their bare theorems while chain families stay bounded;
  - `--use-lemmas` loads a lemma file: certified conclusions appear as `[b]` presumptions
    at depth 0, are overridable by deeper derivation and retractable via the guard atom,
    and the classical limit of the source program is unchanged.
- Atoms with a double-underscore prefix (e.g. lemma guards) are treated as internal:
  they take part in solving but are hidden from per-model output and summaries.

## 2.3.0

- **Redefined `--bnm` branch completion as supervaluational stable completion** (semantic change):
  - the branch's decided literals are read as classical content over base atoms via the
    totality dictionary (`-u=1` ⇔ `u=0`), so no decided literal is silently dropped;
  - stable models of the *original* program are conditioned on that content via clingo
    assumptions (conditioning, not program revision);
  - **all** compatible stable models are enumerated (fixes the previous first-model-only
    completion, which could promote atoms unsoundly);
  - completion is symmetric: an undecided atom is presumed true if it holds in every
    compatible stable model, presumed false if it holds in none;
  - an impossible supposition or an empty compatible-model family yields identity completion.
- Totality universe now collects source atoms from rule statements only: atoms occurring
  solely inside `#show` (or other directive) bodies no longer receive totality axioms, so
  display directives cannot change `--3nd`/`--bnm` model counts.
- CLI fixes: the combined `-n5` short form is recognized in brave/cautious mode; `-k` rejects
  negative depths; added `--version`; syntax errors in input files fail with a clean
  `Parse error:` message instead of a traceback; `UNSATISFIABLE` prints once; brave/cautious
  summaries report the real model count instead of a hardcoded `Models : 1`, omit the
  consequences block (and its `Brave/Cautious : yes` claim) on unsatisfiable runs, and count
  consequences over the same `#show`-filtered view they display (summary goldens regenerated
  accordingly).
- Fixed a cluster of small defects: completion diagnostics now carry `depth`/`program_id` on
  plain `--bnm` runs, Legend lines reflect only displayed markers, underscore-initial strong
  negation is recognized, `atom_signature` counts nested-term arity correctly, and perf
  metrics no longer count the Legend token.
- Added flip-trajectory kernel examples (`flip_tf.lp`, `flip_fut.lp`, `flip_width4.lp`) with
  regression cases pinning the single-crossing trajectory grammar of `--bnm` cautious statuses
  (one presumption→derivation polarity handover, UNDEC interludes sized by refutation width),
  plus the parametric generator `scripts/gen_flip_gadget.py`.

## 2.2.14

- Clarified CLI help so the ordinary-use surface is separated from inspection/debug flags.
- Updated public docs to reflect the smaller everyday CLI path and the internal helper-module split.

## 2.2.13

- Added regression coverage for two high-risk semantic boundaries:
  - `#show` filtering now checked in `all`, `brave`, and `cautious` modes;
  - totality construction now checked against grounded atoms only.
- Fixed `#show` handling in brave/cautious summaries so output filtering is applied consistently across modes.
- Fixed totality universe construction to use grounded runtime atoms plus syntactically ground source atoms, without the previous signature/cartesian over-approximation.
- Cleaned the public CLI help by grouping stable output flags separately from advanced/debug inspection flags.

## 2.2.12

- Added `--detect-max-depth`:
  - computes and prints only the maximum reachable decision depth for the selected mode/input;
  - mode-aware behavior:
    - `--3nd-star`: original grounded program;
    - `--3nd` / `--bnm`: totality-backed core search depth.
- Kept output minimal for depth detection (single integer line), so the flag is script-friendly.

## 2.2.11

- Fixed `#show` handling to use clingo AST parsing and output-only filtering:
  - supports show signatures and conditional show terms (including nested terms);
  - removed regex-based parsing path.
- Fixed totality universe construction:
  - now built from grounded symbols instead of Cartesian products over constants;
  - mode-gated so `--3nd-star` never builds/injects totality.
- Added preprocessing transparency:
  - `--dump-preprocessed <path>` to dump static mode injections;
  - `--print-config` to print resolved run settings and trust-boundary info.
- UX/robustness improvements:
  - clean input-file preflight errors (no traceback for missing files);
  - proper CPU-vs-wall timing reporting;
  - installer warns when PATH resolves `klingo` to a different binary than installed.
- Extended regression harness with targeted checks for:
  - conditional and nested `#show` behavior;
  - totality mode gating;
  - missing-file preflight handling.

## 2.2.10

- Installer updated for system-wide availability by default:
  - `scripts/install.sh` now defaults to `--system` scope (`/usr/local/bin`);
  - added `--user` and `--bin-dir` options;
  - uses `sudo` automatically when needed for system directories.

## 2.2.9

- Focused the repository on implementation, examples, and user-facing docs.
- Added public documentation set:
  - `docs/INSTALLATION.md`
  - `docs/API.md`
- Simplified top-level `README.md` with clear usage and maintenance links.

## 2.2.7

- Added optional completion diagnostics for `--bnm` (exposed via the `KLINGO_COMPLETION_DEBUG` environment variable; there is no `--completion-debug` CLI flag).

## Earlier versions

- Internal development line predating the public release.
