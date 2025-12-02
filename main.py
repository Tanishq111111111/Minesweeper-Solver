# main.py

from __future__ import annotations

from typing import Tuple

from board import Board
from solver.csp_solver import CSPSolver
from solver.probabilistic_solver import ProbabilisticSolver


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


def ask_first_click(board: Board) -> Tuple[int, int]:
    """
    Ask the user for the first click (row, col) using 1-based indices.
    Returns 0-based (row, col).
    """
    while True:
        raw = input(
            f"Enter your first click as 'row col' (1-based, 1 ≤ row ≤ {board.rows}, 1 ≤ col ≤ {board.cols}): "
        ).strip()
        parts = raw.split()
        if len(parts) != 2:
            print("Please enter exactly two integers: row col")
            continue
        try:
            r = int(parts[0]) - 1
            c = int(parts[1]) - 1
        except ValueError:
            print("Row and column must be integers.")
            continue

        if not (0 <= r < board.rows and 0 <= c < board.cols):
            print("That cell is out of bounds. Try again.")
            continue

        return r, c


# ---------------------------------------------------------------------------
# Game setup
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


# ---------------------------------------------------------------------------
# Human game loop
# ---------------------------------------------------------------------------

def run_human_game(board: Board) -> None:
    print("=== Minesweeper (Human Mode) ===")
    print("Commands:")
    print("  o r c   -> open cell at row r, column c (1-based indices)")
    print("  f r c   -> toggle flag at row r, column c")
    print("  q       -> quit")
    print()

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


# ---------------------------------------------------------------------------
# AI game loop
# ---------------------------------------------------------------------------

def run_ai_game(board: Board) -> None:
    print("=== Minesweeper (AI Mode) ===")
    print("You will choose the FIRST click; the AI will play the rest.")
    print(board.render())

    # First click from user (always safe by design)
    first_r, first_c = ask_first_click(board)
    board.open_cell(first_r, first_c)

    print("\nAfter your first click:")
    print(board.render())
    print(f"Mines remaining (estimate): {board.remaining_mines_estimate()}")

    # Instantiate solvers
    csp_solver = CSPSolver()
    prob_solver = ProbabilisticSolver()

    step = 0
    while not board.game_over:
        # Let CSP try first
        moves = csp_solver.play_step(board)

        # If CSP can't find anything, fall back to probabilistic solver
        if not moves and not board.game_over:
            moves = prob_solver.play_step(board)

        if not moves:
            # AI is stuck (no safe logical or probabilistic move found)
            print("\n🤖 AI is stuck and cannot find a safe move.")
            break

        step += 1
        print(f"\nAfter AI step {step}:")
        print(board.render())
        print(f"Mines remaining (estimate): {board.remaining_mines_estimate()}")

    # Final outcome
    if board.game_over:
        if board.win:
            print("\n🤖 AI opened all safe cells. AI wins!")
        else:
            print("\n🤖 AI hit a mine. Game over!")
    else:
        print("\nGame ended with some cells still unknown (AI stopped).")

    print("\nFinal board (mines revealed):")
    print(board.render(reveal_mines=True))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    board = configure_board()

    use_human = ask_yes_no("Do you want to play the game yourself?", default=True)
    if use_human:
        run_human_game(board)
    else:
        run_ai_game(board)


if __name__ == "__main__":
    main()
