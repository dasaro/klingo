# Wason-like Heuristic Transfer

This folder contains a small dataset of Wason-like ASP tasks and a runner that:
1) learns defaults from a high-depth run on `train.lp`,
2) tests the learned defaults at depth 0 on variants,
3) compares against clingo ground truth,
4) reports confirmation/disconfirmation at a higher depth.

## Files
- `train.lp`: training instance.
- `test_same.lp`: same rule as train (sanity check).
- `test1.lp`, `test2.lp`, `test3.lp`: rule variants.
- `learned.lp`: generated defaults (overwritten by the runner).
- `run_wason_transfer.py`: evaluation script.

## Run
```sh
python3 Experiments/wason/run_wason_transfer.py
```

## Metrics
- Accuracy at k=0 = number of *correct decided atoms* / total atoms.
- Confirmation/disconfirmation counts at `k-confirm` from learned defaults.

Ground truth is computed with `clingo --outf=2` on each task.
