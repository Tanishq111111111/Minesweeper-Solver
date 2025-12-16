# tests/performance_metrics.py
from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass

from board import Board
from solver.probabilistic_solver import ProbabilisticSolver

@dataclass
class RunConfig:
    rows: int
    cols: int
    mines: int
    games: int
    name: str

def first_click(rows: int, cols: int) -> tuple[int, int]:
    """Use center-ish start to avoid bias toward corners."""
    return rows // 2, cols // 2

def run_single_game(cfg: RunConfig, seed: int) -> dict:
    """Play one game; return metrics for aggregation."""
    rng_board = random.Random(seed)
    rng_solver = random.Random(seed + 13_37)

    board = Board(cfg.rows, cfg.cols, cfg.mines, rng=rng_board)
    solver = ProbabilisticSolver(rng=rng_solver)

    r0, c0 = first_click(cfg.rows, cfg.cols)
    board.open_cell(r0, c0)

    moves = 0
    start = time.perf_counter()
    while not board.game_over:
        step_moves = solver.play_step(board)
        if not step_moves:
            break  # solver is stuck
        moves += len(step_moves)
    duration = time.perf_counter() - start

    opened = sum(1 for cell in board.iter_cells() if cell.is_open)
    return {"win": board.win, "moves": moves, "opened": opened, "time": duration}

def summarize(cfg: RunConfig, results: list[dict]) -> None:
    wins = sum(1 for r in results if r["win"])
    win_rate = wins / len(results)
    moves = [r["moves"] for r in results]
    times = [r["time"] for r in results]
    opened = [r["opened"] for r in results]

    print(f"\n=== {cfg.name} ({cfg.rows}x{cfg.cols}, {cfg.mines} mines, n={cfg.games}) ===")
    print(f"Win rate: {win_rate:.2%} ({wins}/{len(results)})")
    print(f"Avg moves: {statistics.mean(moves):.1f}")
    print(f"Avg opened cells: {statistics.mean(opened):.1f}")
    print(f"Avg time per game: {statistics.mean(times):.3f}s")

def run_suite(configs: list[RunConfig], base_seed: int = 12345) -> None:
    for cfg in configs:
        results = [run_single_game(cfg, base_seed + i) for i in range(cfg.games)]
        summarize(cfg, results)

if __name__ == "__main__":
    configs = [
        RunConfig(rows=9, cols=9, mines=10, games=200, name="Beginner"),
        RunConfig(rows=16, cols=16, mines=40, games=200, name="Intermediate"),
        RunConfig(rows=16, cols=30, mines=99, games=200, name="Expert"),
    ]
    run_suite(configs)
