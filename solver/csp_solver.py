# solver/csp_solver.py
from __future__ import annotations

from typing import List, Tuple, Set

from board import Board
from .utils import (
    BaseSolver,
    Move,
    Constraint,
    build_constraints,
    basic_logical_moves,
)


class CSPSolver(BaseSolver):
    """
    Constraint-based Minesweeper solver.

    Strategy:
      1. Apply basic local rules (from utils.basic_logical_moves).
      2. If no moves found, apply a simple subset rule on constraints:

         For constraints A and B, if U_A ⊆ U_B:
             rem_A = N_A - F_A
             rem_B = N_B - F_B

             Then cells in U_B \ U_A must contain (rem_B - rem_A) mines.

             - If rem_B - rem_A == 0  -> all cells in (U_B \ U_A) are safe.
             - If rem_B - rem_A == len(U_B \ U_A) -> all are mines.
    """

    def next_moves(self, board: Board) -> List[Move]:
        # 1. Basic rules first
        moves = basic_logical_moves(board)
        if moves:
            return moves

        # 2. Subset reasoning on current constraints
        constraints = build_constraints(board)
        subset_moves = self._subset_reasoning(constraints)

        return subset_moves

    # ------------------------------------------------------------------ #
    # Subset reasoning
    # ------------------------------------------------------------------ #
    def _subset_reasoning(self, constraints: List[Constraint]) -> List[Move]:
        to_open: Set[Tuple[int, int]] = set()
        to_flag: Set[Tuple[int, int]] = set()

        # Precompute sets and remaining mine counts per constraint
        processed: List[Tuple[Constraint, Set[Tuple[int, int]], int]] = []
        for c in constraints:
            unknown_set = set(c.unknown)
            if not unknown_set:
                continue
            remaining = c.clue - c.flagged
            if remaining < 0 or remaining > len(unknown_set):
                # Inconsistent, skip
                continue
            processed.append((c, unknown_set, remaining))

        n = len(processed)
        for i in range(n):
            cA, setA, remA = processed[i]
            for j in range(n):
                if i == j:
                    continue
                cB, setB, remB = processed[j]

                # We only care about strict or non-strict subset relationships
                if not setA.issubset(setB):
                    continue

                diff = setB - setA
                if not diff:
                    continue

                diff_remaining = remB - remA

                if diff_remaining < 0 or diff_remaining > len(diff):
                    continue

                if diff_remaining == 0:
                    # All cells in diff are safe
                    to_open.update(diff)
                elif diff_remaining == len(diff):
                    # All cells in diff are mines
                    to_flag.update(diff)

        moves: List[Move] = []
        for r, c in sorted(to_open):
            moves.append(Move("open", r, c))
        for r, c in sorted(to_flag):
            moves.append(Move("flag", r, c))
        return moves
