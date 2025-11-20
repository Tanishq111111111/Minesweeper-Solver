from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, List, Optional, Tuple


class CellState(Enum):
    """Possible visible states of a cell."""
    UNOPENED = auto()
    OPEN = auto()
    FLAGGED = auto()


@dataclass
class Cell:
    """Represents a single square on the Minesweeper board."""
    row: int
    col: int
    is_mine: bool = False
    adjacent_mines: int = 0
    state: CellState = CellState.UNOPENED

    def reset(self) -> None:
        """Reset this cell to a fresh, non-mine, unopened state."""
        self.is_mine = False
        self.adjacent_mines = 0
        self.state = CellState.UNOPENED

    @property
    def is_open(self) -> bool:
        return self.state == CellState.OPEN

    @property
    def is_flagged(self) -> bool:
        return self.state == CellState.FLAGGED

    def display_char(self, reveal_mines: bool = False) -> str:
        """
        Character for this cell, following the project guidelines.

        - 'U' : unopened
        - 'O' : open, 0 adjacent mines
        - '1'..'8' : open, that many adjacent mines
        - 'F' : flagged
        - 'B' : bomb (when revealed or reveal_mines=True)
        """
        if reveal_mines and self.is_mine:
            return "B"

        if self.state == CellState.FLAGGED:
            return "F"
        if self.state == CellState.UNOPENED:
            return "U"

        # Cell is open at this point
        if self.is_mine:
            # This only happens on game-over / reveal
            return "B"

        return "O" if self.adjacent_mines == 0 else str(self.adjacent_mines)


class Board:
    """
    Backend representation of a Minesweeper board.

    Design:
    - Mines are placed *after* the first click so that the first click is always safe.
    - Coordinates are 0-indexed internally: row in [0, rows-1], col in [0, cols-1].
    - Front-end code (e.g., main.py) can convert to/from 1-indexed if desired.
    """

    def __init__(
        self,
        rows: int = 16,
        cols: int = 16,
        num_mines: int = 80,
        rng: Optional[random.Random] = None,
    ) -> None:
        if rows <= 0 or cols <= 0:
            raise ValueError("Board dimensions must be positive.")
        if num_mines <= 0 or num_mines >= rows * cols:
            raise ValueError("Number of mines must be between 1 and rows*cols-1.")

        self.rows = rows
        self.cols = cols
        self.num_mines = num_mines
        self.rng = rng or random.Random()

        # Game state flags
        self.mines_placed: bool = False
        self.game_over: bool = False
        self.win: bool = False

        # 2D grid of Cell objects
        self.grid: List[List[Cell]] = [
            [Cell(r, c) for c in range(cols)] for r in range(rows)
        ]

    # ------------------------------------------------------------------
    # Core board / cell helpers
    # ------------------------------------------------------------------
    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def get_cell(self, row: int, col: int) -> Cell:
        if not self.in_bounds(row, col):
            raise IndexError(f"Cell ({row}, {col}) is out of bounds.")
        return self.grid[row][col]

    def neighbors(self, row: int, col: int) -> Iterable[Cell]:
        """Yield all neighboring cells (up to 8)."""
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if self.in_bounds(nr, nc):
                    yield self.grid[nr][nc]

    # ------------------------------------------------------------------
    # Mine placement and counts
    # ------------------------------------------------------------------
    def _place_mines(self, first_click: Tuple[int, int]) -> None:
        """
        Randomly place mines on the board, making sure the first click
        is always safe. Mines are placed only once, on the first call
        to open_cell.
        """
        all_positions = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if (r, c) != first_click
        ]

        if self.num_mines > len(all_positions):
            raise ValueError(
                "Not enough cells to place mines while keeping the first click safe."
            )

        mine_positions = set(self.rng.sample(all_positions, self.num_mines))
        for r, c in mine_positions:
            self.grid[r][c].is_mine = True

        self._compute_adjacent_mine_counts()
        self.mines_placed = True

    def _compute_adjacent_mine_counts(self) -> None:
        """Calculate the number of mines around each cell."""
        for row in range(self.rows):
            for col in range(self.cols):
                cell = self.grid[row][col]
                if cell.is_mine:
                    cell.adjacent_mines = 0
                    continue
                count = sum(1 for n in self.neighbors(row, col) if n.is_mine)
                cell.adjacent_mines = count

    # ------------------------------------------------------------------
    # Game actions: open / flag cells
    # ------------------------------------------------------------------
    def open_cell(self, row: int, col: int) -> None:
        """
        Open the cell at (row, col).

        - On the first move, this triggers mine placement.
        - If the opened cell is a mine, the game is lost.
        - If the opened cell has 0 adjacent mines, a flood-fill is performed.
        """
        if not self.in_bounds(row, col):
            raise IndexError(f"Cell ({row}, {col}) is out of bounds.")
        if self.game_over:
            return

        if not self.mines_placed:
            self._place_mines(first_click=(row, col))

        cell = self.grid[row][col]
        if cell.is_flagged or cell.is_open:
            return


        if cell.is_mine:
            # Stepped on a mine -> game over
            cell.state = CellState.OPEN
            self.game_over = True
            self.win = False
            return

        self._flood_fill_open(row, col)

        # Check win condition: all safe cells opened
        if self._all_safe_cells_opened():
            self.game_over = True
            self.win = True

    def _flood_fill_open(self, start_row: int, start_col: int) -> None:
        """
        Open a region of safe cells with 0 adjacent mines, plus their
        boundary of numbered cells (standard Minesweeper behaviour).
        """
        stack: List[Tuple[int, int]] = [(start_row, start_col)]

        while stack:
            row, col = stack.pop()
            cell = self.grid[row][col]

            if cell.is_open or cell.is_flagged or cell.is_mine:
                continue

            cell.state = CellState.OPEN

            # If this cell has no adjacent mines, also open its neighbors
            if cell.adjacent_mines == 0:
                for neighbor in self.neighbors(row, col):
                    if (
                        not neighbor.is_open
                        and not neighbor.is_flagged
                        and not neighbor.is_mine
                    ):
                        stack.append((neighbor.row, neighbor.col))

    def flag_cell(self, row: int, col: int) -> None:
        """
        Toggle a flag on the given cell.
        Flags can only be placed on unopened cells.
        """
        if not self.in_bounds(row, col):
            raise IndexError(f"Cell ({row}, {col}) is out of bounds.")
        if self.game_over:
            return

        cell = self.grid[row][col]
        if cell.is_open:
            return

        if cell.state == CellState.UNOPENED:
            cell.state = CellState.FLAGGED
        elif cell.state == CellState.FLAGGED:
            cell.state = CellState.UNOPENED

    # ------------------------------------------------------------------
    # Queries (useful for solvers & tests)
    # ------------------------------------------------------------------
    def _all_safe_cells_opened(self) -> bool:
        """True iff every non-mine cell is open."""
        for row in range(self.rows):
            for col in range(self.cols):
                cell = self.grid[row][col]
                if not cell.is_mine and not cell.is_open:
                    return False
        return True

    def unopened_cells(self) -> Iterable[Cell]:
        """Iterate over all currently unopened (and unflagged) cells."""
        for row in self.grid:
            for cell in row:
                if cell.state == CellState.UNOPENED:
                    yield cell

    def iter_cells(self) -> Iterable[Cell]:
        """Iterate over all cells in row-major order."""
        for row in self.grid:
            for cell in row:
                yield cell

    def count_flags(self) -> int:
        """Count how many cells are flagged."""
        return sum(
            1 for row in self.grid for cell in row if cell.state == CellState.FLAGGED
        )

    def remaining_mines_estimate(self) -> int:
        """
        How many mines *should* remain, assuming every flag is correct.
        Mainly for UI/debugging, not strict rule enforcement.
        """
        return self.num_mines - self.count_flags()

    def reveal_all_mines(self) -> None:
        """
        Mark all mines as open (for final board reveal).
        This does not change win/lose state; call after the game ends.
        """
        for row in self.grid:
            for cell in row:
                if cell.is_mine:
                    cell.state = CellState.OPEN

    # ------------------------------------------------------------------
    # Rendering helpers (terminal front-end can just print(board))
    # ------------------------------------------------------------------
    def to_display_grid(self, reveal_mines: bool = False) -> List[List[str]]:
        """
        Return a 2D list of characters representing the board, using:

        - 'U' for unopened cells
        - 'O' for open cells with 0 adjacent mines
        - '1'..'8' for open numbered cells
        - 'F' for flags
        - 'B' for bombs (when reveal_mines=True or on an opened mine)
        """
        return [
            [
                self.grid[r][c].display_char(
                    reveal_mines=reveal_mines or self.game_over
                )
                for c in range(self.cols)
            ]
            for r in range(self.rows)
        ]

    def __str__(self) -> str:
        """Pretty ASCII representation for terminal output."""
        return self.render()

    def render(self, reveal_mines: bool = False) -> str:
        """
        Render the board as a multiline string, e.g.:

        ________________________________
        [U][U][2][U][O][U]
        [U][U][2][U][U][U]
        ________________________________
        """
        grid = self.to_display_grid(reveal_mines=reveal_mines)
        # Simple border whose length scales with the number of columns
        border_len = self.cols * 3 + 2
        border = "_" * border_len

        lines = [border]
        for r in range(self.rows):
            line = "".join(f"[{grid[r][c]}]" for c in range(self.cols))
            lines.append(line)
        lines.append(border)
        return "\n".join(lines)
