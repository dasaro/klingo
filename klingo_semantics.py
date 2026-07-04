"""
Compatibility facade for semantics helpers.

New code should import from the focused modules:
  - klingo_show
  - klingo_totality
  - klingo_completion
"""

from klingo_completion import ClingoCompletionEngine, apply_default_completion
from klingo_show import (
    ShowFilter,
    ShowTermRule,
    atom_signature,
    extract_show_filter,
    filter_valuation_by_show,
    parse_show_signatures,
)
from klingo_totality import (
    add_classical_totality_backend,
    build_totality_universe,
    build_totality_universe_from_control,
    render_totality_rules,
)

__all__ = [
    "ClingoCompletionEngine",
    "ShowFilter",
    "ShowTermRule",
    "add_classical_totality_backend",
    "apply_default_completion",
    "atom_signature",
    "build_totality_universe",
    "build_totality_universe_from_control",
    "extract_show_filter",
    "filter_valuation_by_show",
    "parse_show_signatures",
    "render_totality_rules",
]
