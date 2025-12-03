# solver/utils.py
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Literal, Dict

from board import Board, CellState, Cell


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

ActionType = Literal["open", "flag"]


@dataclass(frozen=True)
class Move:
    """A single solver action on the board."""
    action: ActionType
    row: int
    col: int


@dataclass
class Constraint:
    """
    A constraint derived from a numbered open cell.

    clue         : number on the cell (adjacent mine count)
    unknown      : list of (row, col) coords of unopened & unflagged neighbors
    flagged      : number of flagged neighbors
    """
    row: int
    col: int
    clue: int
    unknown: List[Tuple[int, int]]
    flagged: int


# ---------------------------------------------------------------------------
# Base solver interface
# ---------------------------------------------------------------------------

class BaseSolver(ABC):
    """
    Abstract base class for all AI solvers.

    Typical usage:
        solver = SomeSolver()
        while not board.game_over:
            solver.play_step(board)
    """

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    @abstractmethod
    def next_moves(self, board: Board) -> List[Move]:
        """
        Compute the next moves for the solver to play.
        This method MUST NOT modify the board.
        """
        raise NotImplementedError

    def play_step(self, board: Board) -> List[Move]:
        """
        Compute moves via next_moves(...) and apply them to the board.

        Returns the list of moves actually applied.
        """
        moves = self.next_moves(board)

        for move in moves:
            if move.action == "open":
                board.open_cell(move.row, move.col)
            elif move.action == "flag":
                board.flag_cell(move.row, move.col)
            else:
                raise ValueError(f"Unknown action: {move.action}")

        return moves

    def play_game(self, board: Board, max_steps: Optional[int] = None) -> None:
        """
        Let this solver play automatically until:
          - the game is over, or
          - it gets stuck (no moves), or
          - max_steps is reached (if provided).
        """
        steps = 0
        while not board.game_over:
            moves = self.play_step(board)
            if not moves:
                break
            steps += 1
            if max_steps is not None and steps >= max_steps:
                break


# ---------------------------------------------------------------------------
# Board / neighborhood helpers
# ---------------------------------------------------------------------------

def get_unopened_neighbors(board: Board, row: int, col: int) -> List[Cell]:
    return [
        n for n in board.neighbors(row, col)
        if n.state == CellState.UNOPENED
    ]


def get_flagged_neighbors(board: Board, row: int, col: int) -> List[Cell]:
    return [
        n for n in board.neighbors(row, col)
        if n.state == CellState.FLAGGED
    ]


def get_unknown_neighbors(board: Board, row: int, col: int) -> List[Cell]:
    """
    Unknown = unopened and unflagged neighbors.
    """
    return [
        n for n in board.neighbors(row, col)
        if n.state == CellState.UNOPENED
    ]


def get_frontier_cells(board: Board) -> List[Cell]:
    """
    Frontier cells are open, numbered cells that touch at least one
    unopened neighbor.
    """
    frontier: List[Cell] = []
    for cell in board.iter_cells():
        if not cell.is_open:
            continue
        if cell.is_mine:
            continue
        if cell.adjacent_mines == 0:
            continue
        if get_unknown_neighbors(board, cell.row, cell.col):
            frontier.append(cell)
    return frontier


# ---------------------------------------------------------------------------
# Constraint extraction
# ---------------------------------------------------------------------------

def build_constraints(board: Board) -> List[Constraint]:
    """
    Build a list of constraints from the current board state.
    Only open, numbered frontier cells contribute constraints.
    """
    constraints: List[Constraint] = []

    for cell in get_frontier_cells(board):
        unknown_neighbors = get_unknown_neighbors(board, cell.row, cell.col)
        if not unknown_neighbors:
            continue

        flagged_neighbors = get_flagged_neighbors(board, cell.row, cell.col)
        constraints.append(
            Constraint(
                row=cell.row,
                col=cell.col,
                clue=cell.adjacent_mines,
                unknown=[(n.row, n.col) for n in unknown_neighbors],
                flagged=len(flagged_neighbors),
            )
        )

    return constraints


# ---------------------------------------------------------------------------
# Basic deterministic logic (used by both CSP & probabilistic solvers)
# ---------------------------------------------------------------------------

def basic_logical_moves(board: Board) -> List[Move]:
    """
    Apply the two classic local Minesweeper rules:

    For each frontier cell with clue N:
      U = unopened neighbors, F = flagged neighbors, R = N - F

      1. If R == 0, all U are safe -> open them.
      2. If R == len(U), all U are mines -> flag them.

    Returns a list of deduced moves. Does not modify the board.
    """
    constraints = build_constraints(board)
    to_open: set[Tuple[int, int]] = set()
    to_flag: set[Tuple[int, int]] = set()

    for c in constraints:
        remaining = c.clue - c.flagged
        if remaining < 0 or remaining > len(c.unknown):
            # Inconsistent constraint (likely due to bad flags); skip it.
            continue

        if remaining == 0:
            # All unknown neighbors are safe
            for coord in c.unknown:
                to_open.add(coord)
        elif remaining == len(c.unknown):
            # All unknown neighbors are mines
            for coord in c.unknown:
                to_flag.add(coord)

    moves: List[Move] = []
    for r, c in sorted(to_open):
        moves.append(Move("open", r, c))
    for r, c in sorted(to_flag):
        moves.append(Move("flag", r, c))

    return moves


# ---------------------------------------------------------------------------
# Probability helpers
# ---------------------------------------------------------------------------

def count_flags(board: Board) -> int:
    return board.count_flags()


def remaining_mines(board: Board) -> int:
    """Estimated remaining mines, assuming flags are correct."""
    return board.num_mines - count_flags(board)


def unopened_cells(board: Board) -> List[Cell]:
    return list(board.unopened_cells())


def global_mine_density(board: Board) -> float:
    """
    Baseline estimate:
        remaining_mines / remaining_unopened_cells
    Returns 0.0 if there are no unopened cells.
    """
    cells = unopened_cells(board)
    if not cells:
        return 0.0
    rem_mines = remaining_mines(board)
    rem_mines = max(0, rem_mines)
    return rem_mines / len(cells)

def constraint_components(constraints: list[Constraint]) -> list[list[Constraint]]:
    graph: dict[int, set[int]] = {i: set() for i in range(len(constraints))}
    for i, ci in enumerate(constraints):
        set_i = set(ci.unknown)
        for j in range(i + 1, len(constraints)):
            if set_i.intersection(constraints[j].unknown):
                graph[i].add(j)
                graph[j].add(i)

    comps: list[list[int]] = []
    seen: set[int] = set()
    for i in range(len(constraints)):
        if i in seen:
            continue
        stack = [i]; seen.add(i); comp = []
        while stack:
            node = stack.pop()
            comp.append(node)
            for nei in graph[node]:
                if nei not in seen:
                    seen.add(nei); stack.append(nei)
        comps.append(comp)
    return [[constraints[i] for i in comp] for comp in comps]

