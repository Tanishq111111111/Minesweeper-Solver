# tests/test_board_init.py

import pytest

from board import Board, CellState


def test_default_board_initialization():
    """Default board should be 16x16 with 80 mines and clean initial state."""
    board = Board()  # uses default rows=16, cols=16, num_mines=80

    assert board.rows == 16
    assert board.cols == 16
    assert board.num_mines == 80

    # Global state flags
    assert board.mines_placed is False
    assert board.game_over is False
    assert board.win is False

    # Every cell should be clean and unopened
    for cell in board.iter_cells():
        assert cell.state == CellState.UNOPENED
        assert cell.is_mine is False
        assert cell.adjacent_mines == 0


def test_custom_board_initialization():
    """Board size and mine count should be configurable."""
    board = Board(rows=10, cols=12, num_mines=20)

    assert board.rows == 10
    assert board.cols == 12
    assert board.num_mines == 20

    # Still no mines before the first click
    assert board.mines_placed is False
    assert sum(1 for c in board.iter_cells() if c.is_mine) == 0


def test_mines_are_placed_after_first_click_and_first_click_is_safe():
    """Mines must be placed lazily and never on the first clicked cell."""
    board = Board()

    first_row, first_col = 3, 5
    board.open_cell(first_row, first_col)

    assert board.mines_placed is True

    # Total number of mines is correct
    mine_count = sum(1 for c in board.iter_cells() if c.is_mine)
    assert mine_count == board.num_mines

    # First clicked cell is never a mine
    first_cell = board.get_cell(first_row, first_col)
    assert first_cell.is_mine is False
    assert first_cell.is_open is True


def test_adjacent_mine_counts_are_consistent_after_placement():
    """Each cell's adjacent_mines should match the actual number of neighboring mines."""
    board = Board()
    board.open_cell(0, 0)  # trigger mine placement

    def naive_neighbor_mine_count(r: int, c: int) -> int:
        count = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < board.rows and 0 <= nc < board.cols:
                    if board.get_cell(nr, nc).is_mine:
                        count += 1
        return count

    for r in range(board.rows):
        for c in range(board.cols):
            cell = board.get_cell(r, c)
            if not cell.is_mine:
                assert cell.adjacent_mines == naive_neighbor_mine_count(r, c)


def test_invalid_board_parameters_raise_value_error():
    """Bad dimensions or mine counts should fail fast."""
    with pytest.raises(ValueError):
        Board(rows=0, cols=5, num_mines=1)

    with pytest.raises(ValueError):
        Board(rows=5, cols=5, num_mines=0)

    with pytest.raises(ValueError):
        # Too many mines (one cell must be safe for the first click)
        Board(rows=5, cols=5, num_mines=25)
