# Examples Kernel

This repository keeps a small, non-overlapping kernel under `Examples/kernel/`.  
Each file demonstrates one specific property.

## Files and Purpose

- `Examples/kernel/asp_convergence.lp`:
  - `--3nd-star` convergence target against plain `clingo`.
- `Examples/kernel/bnm_totality.lp`:
  - `--bnm` convergence target against `clingo` on `(program + totality axioms)`.
- `Examples/kernel/bnm_children_flip.lp`:
  - depth-sensitive belief shift under `--bnm`.
- `Examples/kernel/enum_modes.lp`:
  - differences between `--mode all|brave|cautious`.
- `Examples/kernel/unsat.lp`:
  - unsatisfiable detection.

## Verification Commands

```sh
# 3nd-star (k large enough) vs plain clingo
python3 klingo --3nd-star -k 2 -n 0 --mode brave Examples/kernel/asp_convergence.lp
clingo Examples/kernel/asp_convergence.lp -n 0 --enum-mode=brave

# bnm vs clingo + totality axioms
python3 klingo --bnm -k 2 -n 0 --mode brave Examples/kernel/bnm_totality.lp
cat > /tmp/totality.lp <<'EOF'
1 { p(a); -p(a) } 1.
1 { p(b); -p(b) } 1.
EOF
clingo Examples/kernel/bnm_totality.lp /tmp/totality.lp -n 0 --enum-mode=brave

# depth-sensitive bnm behavior
python3 klingo --bnm -k 0 -n 1 Examples/kernel/bnm_children_flip.lp --no-clingo-output
python3 klingo --bnm -k 1 -n 1 Examples/kernel/bnm_children_flip.lp --no-clingo-output

# enumeration modes
python3 klingo --3nd-star -k 2 -n 0 --mode all Examples/kernel/enum_modes.lp
python3 klingo --3nd-star -k 2 -n 0 --mode brave Examples/kernel/enum_modes.lp
python3 klingo --3nd-star -k 2 -n 0 --mode cautious Examples/kernel/enum_modes.lp

# unsat
python3 klingo --3nd-star -k 0 Examples/kernel/unsat.lp
```
