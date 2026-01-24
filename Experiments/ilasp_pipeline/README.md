# ILASP Pipeline (k-lingo → examples → ILASP → learned rules)

This folder implements a first pass at the self‑supervised ILASP pipeline described in
`docs/klingo_heuristic_ilasp_plan.md`.

## Files
- `generate_examples.py`: runs k‑lingo at high depth, extracts positives/negatives, and writes ILASP examples.
- `mode_bias.las`: a minimal ILASP bias file (mode declarations) for unary predicates.
- `run_ilasp.sh`: end‑to‑end script that builds examples and runs ILASP.

## Usage
```sh
# 1) Generate examples from a program
python3 Experiments/ilasp_pipeline/generate_examples.py \
  --program Experiments/wason/rule_level/train.lp \
  --k 5 \
  --out Experiments/ilasp_pipeline/examples.las

# 2) Run ILASP to learn rules
./Experiments/ilasp_pipeline/run_ilasp.sh \
  Experiments/ilasp_pipeline/mode_bias.las \
  Experiments/ilasp_pipeline/examples.las \
  Experiments/ilasp_pipeline/learned_rules.lp
```

Notes:
- This first iteration only learns unary rules of the form `q(X) :- p(X), not -q(X).`.
- Examples are generated from cautious (positives) and universal negatives (false in all high‑k models).
- `k` should be high enough to approximate the intended depth of reasoning.
- The runner uses `ILASP --version=4`.
