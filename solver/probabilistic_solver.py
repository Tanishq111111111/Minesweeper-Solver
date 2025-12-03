# solver/probabilistic_solver.py
from __future__ import annotations
from itertools import combinations

import math
from typing import Dict, List, Tuple, Optional

from board import Board
from .utils import (
    BaseSolver,
    Move,
    basic_logical_moves,
    build_constraints,
    unopened_cells,
    global_mine_density,
    constraint_components,
    Constraint,
)


MAX_ENUM_UNKNOWNS = 15


def exact_component_probs(component: list[Constraint]) -> Optional[dict[tuple[int, int], float]]:
    """Enumerate exact mine probabilities for a small constraint component."""
    unknowns = sorted({coord for c in component for coord in c.unknown})
    if len(unknowns) > MAX_ENUM_UNKNOWNS:
        return None

    idx = {coord: i for i, coord in enumerate(unknowns)}
    counts = {coord: 0 for coord in unknowns}
    total = 0

    # brute force assignments that satisfy all constraints
    for mines_count in range(len(unknowns) + 1):
        for mine_indices in combinations(range(len(unknowns)), mines_count):
            assignment = [False] * len(unknowns)
            for k in mine_indices:
                assignment[k] = True

            valid = True
            for c in component:
                mines = sum(assignment[idx[u]] for u in c.unknown) + c.flagged
                if mines != c.clue:
                    valid = False
                    break

            if not valid:
                continue

            total += 1
            for coord in unknowns:
                if assignment[idx[coord]]:
                    counts[coord] += 1

    if total == 0:
        return None
    return {coord: counts[coord] / total for coord in unknowns}


class ProbabilisticSolver(BaseSolver):
    """
    Solver that uses simple probability estimates to choose the safest cell
    to open when deterministic logic fails.

    Strategy:
      1. Try basic logical moves (identical to CSPSolver's first step).
      2. If none:
         - For each constraint (numbered frontier cell):
             U = unknown neighbors, F = flagged neighbors, rem = N - F
             each cell in U gets a local probability rem / len(U).
         - Combine multiple local probabilities per cell by taking the max
           (pessimistic).
         - For cells with no local info, use global mine density.
         - Choose the cell with the minimum probability of being a mine
           and open it.
    """

    def next_moves(self, board: Board) -> List[Move]:
        # 1. Deterministic moves first
        moves = basic_logical_moves(board)
        if moves:
            return moves

        # 2. Probability-based guess
        return self._probabilistic_move(board)

    # ------------------------------------------------------------------ #
    # Probability logic
    # ------------------------------------------------------------------ #
    def _probabilistic_move(self, board: Board) -> List[Move]:
        # If game already over, nothing to do
        if board.game_over:
            return []

        # Collect all unopened cells
        unopened = unopened_cells(board)
        if not unopened:
            return []

        # Build constraints and split into connected components
        constraints = build_constraints(board)
        comps = constraint_components(constraints)

        # Per-cell probability estimates from exact/MC per component
        comp_probs: Dict[Tuple[int, int], float] = {}
        for comp in comps:
            exact = exact_component_probs(comp)
            if exact:
                comp_probs.update(exact)

        # Baseline probability for cells with no component info
        base_p = global_mine_density(board)

        frontier_cells = {coord for comp in comps for c in comp for coord in c.unknown}
        cell_prob: Dict[Tuple[int, int], float] = {}

        for cell in unopened:
            coord = (cell.row, cell.col)
            if coord in comp_probs:
                p = comp_probs[coord]
            else:
                p = base_p
            cell_prob[coord] = max(0.0, min(1.0, p))  # clamp

        if not cell_prob:
            return []

        # Choose cell with minimum probability
        min_p = min(cell_prob.values())
        candidates = [coord for coord, p in cell_prob.items() if math.isclose(p, min_p, rel_tol=1e-9) or p == min_p]

        # Risk gate: if everything is risky, prefer cells outside the frontier when possible
        RISK_GATE = 0.25
        if min_p > RISK_GATE:
            outside = [coord for coord in candidates if coord not in frontier_cells]
            if outside:
                candidates = outside

        chosen_r, chosen_c = self.rng.choice(candidates)
        return [Move("open", chosen_r, chosen_c)]

