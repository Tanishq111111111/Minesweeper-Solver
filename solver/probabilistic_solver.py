# solver/probabilistic_solver.py
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from board import Board, CellState
from .utils import (
    BaseSolver,
    Move,
    basic_logical_moves,
    build_constraints,
    remaining_mines,
    unopened_cells,
    global_mine_density,
)


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

        # Build local probability estimates from constraints
        constraints = build_constraints(board)
        local_probs: Dict[Tuple[int, int], List[float]] = {}

        for c in constraints:
            remaining = c.clue - c.flagged
            if remaining < 0 or remaining > len(c.unknown) or not c.unknown:
                continue

            p_local = remaining / len(c.unknown)
            for coord in c.unknown:
                local_probs.setdefault(coord, []).append(p_local)

        # Baseline probability for unknown cells with no local info
        base_p = global_mine_density(board)

        # Combine probabilities per cell
        cell_prob: Dict[Tuple[int, int], float] = {}

        for cell in unopened:
            coord = (cell.row, cell.col)
            probs = local_probs.get(coord)

            if probs:
                # Take the maximum local estimate (pessimistic approach)
                p = max(probs)
            else:
                p = base_p

            # Clamp to [0, 1] for sanity
            p = max(0.0, min(1.0, p))
            cell_prob[coord] = p

        if not cell_prob:
            return []

        # Choose cell with minimum probability
        min_p = min(cell_prob.values())
        best_coords = [coord for coord, p in cell_prob.items() if math.isclose(p, min_p, rel_tol=1e-9) or p == min_p]

        # Random tiebreaker among best candidates
        chosen_r, chosen_c = self.rng.choice(best_coords)

        return [Move("open", chosen_r, chosen_c)]
