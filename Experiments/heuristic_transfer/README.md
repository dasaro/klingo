# Heuristic Transfer (BNM)

This experiment saves high-depth consequences as defeasible defaults, then reuses them on related programs.

## Files
- `base.lp`: source problem used to learn defaults.
- `target_help.lp`: related problem where learned defaults help.
- `target_mislead.lp`: related problem where learned defaults are overridden at higher depth (via `s/t` loop).
- `learn_defaults.py`: extracts brave consequences from `klingo --bnm` and writes a defeasible defaults file.

## Workflow
1) Learn defaults from a deep run (choose a large k):

```sh
python3 learn_defaults.py --input base.lp --k 3 --output learned.lp
```

2) Solve a related task with and without learned defaults:

```sh
./klingo --bnm -k 1 target_help.lp
./klingo --bnm --heuristics learned.lp -k 1 target_help.lp
```

3) Increase depth when defaults mislead:

```sh
./klingo --bnm --heuristics learned.lp -k 1 target_mislead.lp
./klingo --bnm --heuristics learned.lp -k 2 target_mislead.lp
```

## Notes
- The learned file encodes defeasible defaults as rules of the form `a :- not -a.`.
- Strongly negated atoms are encoded as `-a :- not a.`.
- Defaults are only used to complete undecided atoms; higher depth can override them.
