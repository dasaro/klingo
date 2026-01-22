# Heuristic Learning via ILASP: Plan

## Goal
Turn high‑depth k‑lingo outcomes into a principled rule‑learning pipeline using ILASP. The intent is to learn general rules (e.g., `flip(C) :- red(C), not -flip(C).`) rather than only instance‑specific defaults.

## Why ILASP
- ILASP can learn ASP rules with default negation.
- It supports explicit hypothesis spaces and background knowledge.
- It can encode preferences, exceptions, and constraints.

## Data Generation Strategy (Self‑Supervised)
We do not assume labeled examples. Instead, we **generate** positives/negatives from k‑lingo itself.

### For each instance
1) Run k‑lingo at a **high depth** (k ≫ 0).
2) Extract consequences:
   - **Positive (certain):** cautious consequences at high k.
   - **Negative (certain):** atoms false in all high‑k models.
   - **Ambiguous:** brave‑only atoms (leave unlabeled or mark as "possible").
3) Optionally generate counterfactuals (remove/flip facts) to create stronger negative evidence.

### Labels
- Positive example: `#pos{ atom }.`
- Negative example: `#neg{ atom }.`
- Use a consistent predicate schema per task family.

## Background Knowledge
- Instance facts (e.g., `red(c1).`), plus domain axioms.
- Optional: structural constraints (e.g., "only one card can be flipped").

## Hypothesis Space (Bias)
Start conservatively:
- Unary rules with one body predicate:
  - `q(X) :- p(X), not -q(X).`
- Optional extension:
  - Binary predicates,
  - Conjunctions of 2 predicates,
  - Explicit exceptions.

## Training Loop
1) Generate dataset of instances.
2) For each instance, generate positives/negatives from high‑k run.
3) Feed ILASP with:
   - Background knowledge
   - Examples
   - Bias / mode declarations
4) Output learned rules.

## Evaluation
- Apply learned rules to **new instances** at k=0.
- Measure:
  - All‑models max accuracy vs clingo,
  - Decided atoms at k=0,
  - Confirmation/disconfirmation at higher k.

## Deliverables
- `scripts/ilasp/` pipeline
- `experiments/` dataset generator
- `learned_rules.lp` outputs
- Benchmarks comparing k=0 with/without learned rules
