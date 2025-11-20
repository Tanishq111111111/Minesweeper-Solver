# main.py

from __future__ import annotations

from typing import Tuple

from board import Board  # or: from Board import Board  (if you use capital B)


# ---------------------------------------------------------------------------
# Helper functions for user input
# ---------------------------------------------------------------------------

def ask_yes_no(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter 'y' or 'n'.")


def ask_int(prompt: str, minimum: int, maximum: int, default: int) -> int:
    full_prompt = f"{prompt} (min={minimum}, max={maximum}, default={default}): "
    while True:
        raw = input(full_prompt).strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Please enter an integer.")
            continue
        if not (minimum <= value <= maximum):
            print(f"Value must be between {minimum} and {maximum}.")
            continue
        return value


def parse_move(user_input: str) -> Tuple[str, int, int]:
    """
    Parse a move string like:
      'o 3 4' or 'open 3 4'  -> open cell (row=3, col=4)
      'f 3 4' or 'flag 3 4'  -> toggle flag

    Returns: (action, row_index, col_index) where row/col are 0-based.

    Raises ValueError on bad input.
    """
    tokens = user_input.strip().split()
    if not tokens:
        raise ValueError("Empty input.")

    action_token = tokens[0].lower()
    if action_token in {"q", "quit", "exit"}:
        return ("quit", -1, -1)

    if len(tokens) != 3:
        raise ValueError("Format must be: 'o row col' or 'f row col' (or 'q' to quit).")

    if action_token in {"o", "open"}:
        action = "open"
    elif action_token in {"f", "flag"}:
        action = "flag"
    else:
        raise ValueError("First token must be 'o'/'open', 'f'/'flag', or 'q' to quit.")

    try:
        # User enters 1-based coordinates; convert to 0-based
        row = int(tokens[1]) - 1
        col = int(tokens[2]) - 1
    except ValueError:
        raise ValueError("Row and column must be integers.")

    return (action, row, col)


# ---------------------------------------------------------------------------
# Game loop
# ---------------------------------------------------------------------------

def configure_board() -> Board:
    """Ask the user for board size and mine count, with good defaults."""
    print("=== Minesweeper Configuration ===")
    use_default = not ask_yes_no("Do you want to customize the board?", default=False)

    if use_default:
        rows, cols, mines = 16, 16, 80
    else:
        rows = ask_int("Number of rows", minimum=2, maximum=50, default=16)
        cols = ask_int("Number of columns", minimum=2, maximum=50, default=16)

        max_mines = rows * cols - 1  # at least one safe cell for first click
        default_mines = max(1, (rows * cols) // 5)  # ~20% of cells as a heuristic
        if default_mines > max_mines:
            default_mines = max_mines

        mines = ask_int("Number of mines", minimum=1, maximum=max_mines, default=default_mines)

    print(f"\nCreating a {rows}x{cols} board with {mines} mines...\n")
    return Board(rows=rows, cols=cols, num_mines=mines)


def main() -> None:
    board = configure_board()

    print("=== Minesweeper ===")
    print("Commands:")
    print("  o r c   -> open cell at row r, column c (1-based indices)")
    print("  f r c   -> toggle flag at row r, column c")
    print("  q       -> quit")
    print()

    # Main game loop
    while True:
        # Show current board
        print(board.render())
        print(f"Mines remaining (estimate): {board.remaining_mines_estimate()}")

        # If the game is already over, show final result and break
        if board.game_over:
            if board.win:
                print("\n🎉 You opened all safe cells. You win!")
            else:
                print("\n💥 You hit a mine. Game over!")
            # Final reveal (mines already shown via board.game_over flag)
            print("\nFinal board:")
            print(board.render(reveal_mines=True))
            break

        # Ask for the next move
        user_input = input("\nEnter your move: ")

        try:
            action, row, col = parse_move(user_input)
        except ValueError as exc:
            print(f"Invalid move: {exc}")
            continue

        if action == "quit":
            print("Goodbye!")
            break

        # Bounds check
        if not (0 <= row < board.rows and 0 <= col < board.cols):
            print(f"Cell ({row + 1}, {col + 1}) is out of bounds.")
            continue

        # Apply the action
        if action == "open":
            board.open_cell(row, col)
        elif action == "flag":
            board.flag_cell(row, col)


if __name__ == "__main__":
    main()



