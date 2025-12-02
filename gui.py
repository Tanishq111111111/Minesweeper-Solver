# gui.py
import os
import cv2
from PIL import Image, ImageTk

import tkinter as tk
from tkinter import messagebox

from board import Board, CellState
from solver.csp_solver import CSPSolver
from solver.probabilistic_solver import ProbabilisticSolver

CELL_SIZE = 28
BOARD_BORDER = 2
CANVAS_BG = "black"
CELL_CLOSED = "#b0b0b0"
CELL_OPEN = "#dcdcdc"
FLAG_GLYPH = "🚩"

NUMBER_COLORS = {
    1: "#0b24fb",
    2: "#0f7b0f",
    3: "#e00b0b",
    4: "#0b0b76",
    5: "#6e0909",
    6: "#0b7676",
    7: "#000000",
    8: "#4d4d4d",
}

class VideoPopup(tk.Toplevel):
    def __init__(self, master, video_path: str, title: str = "Video"):
        super().__init__(master)
        self.title(title)
        self.configure(bg="black")
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            tk.Label(self, text="Unable to open video", fg="white", bg="black").pack(padx=10, pady=10)
            return
        self.label = tk.Label(self, bg="black")
        self.label.pack()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._playing = True
        self._play_next_frame()

    def _play_next_frame(self):
        if not self._playing:
            return
        ret, frame = self.cap.read()
        if not ret:
            # loop video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        imgtk = ImageTk.PhotoImage(image=img)
        self.label.configure(image=imgtk)
        self.label.image = imgtk
        self.after(33, self._play_next_frame)  # ~30 fps

    def on_close(self):
        self._playing = False
        if self.cap:
            self.cap.release()
        self.destroy()


class MinesweeperUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Minesweeper Solver GUI")
        self.configure(bg="#1a1a1a")

        self.board: Board | None = None
        self.csp_solver = CSPSolver()
        self.prob_solver = ProbabilisticSolver()

        self.rows_var = tk.IntVar(value=16)
        self.cols_var = tk.IntVar(value=16)
        self.mines_var = tk.IntVar(value=40)
        self.mines_left_var = tk.StringVar(value="Mines left: -")
        self.last_solver_message: str = ""

        self._build_controls()
        self._build_canvas()
        self.new_game()
        self._game_over_shown = False  # in __init__


    # UI setup
    def _build_controls(self) -> None:
        top = tk.Frame(self, bg="#1a1a1a")
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

        tk.Label(top, text="Rows", fg="white", bg="#1a1a1a").pack(side=tk.LEFT)
        tk.Entry(top, width=4, textvariable=self.rows_var).pack(side=tk.LEFT, padx=4)

        tk.Label(top, text="Cols", fg="white", bg="#1a1a1a").pack(side=tk.LEFT)
        tk.Entry(top, width=4, textvariable=self.cols_var).pack(side=tk.LEFT, padx=4)

        tk.Label(top, text="Mines", fg="white", bg="#1a1a1a").pack(side=tk.LEFT)
        tk.Entry(top, width=5, textvariable=self.mines_var).pack(side=tk.LEFT, padx=4)

        tk.Button(top, text="New Game", command=self.new_game).pack(side=tk.LEFT, padx=8)
        tk.Button(top, text="AI Step", command=self.ai_step).pack(side=tk.LEFT, padx=4)

        tk.Label(top, textvariable=self.mines_left_var, fg="white", bg="#1a1a1a").pack(
            side=tk.RIGHT, padx=4
        )
    
    def _maybe_show_game_over(self):
        if not self.board or not self.board.game_over or self._game_over_shown:
            return
        self._game_over_shown = True
        if self.board.win:
            VideoPopup(self, "assets\win.mp4", title="You win! 🎉")
        else:
            self.board.reveal_all_mines()
            VideoPopup(self, "assets\lose.mp4", title="Boom! 💥")


    def _build_canvas(self) -> None:
        self.canvas = tk.Canvas(
            self,
            bg=CANVAS_BG,
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.TOP, padx=8, pady=8)
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        # Shift+Left for flag on mac/trackpads that lack right-click
        self.canvas.bind("<Shift-Button-1>", self.on_right_click)

    # Game lifecycle
    def new_game(self) -> None:
        rows = max(2, self.rows_var.get())
        cols = max(2, self.cols_var.get())
        mines = max(1, min(self.mines_var.get(), rows * cols - 1))

        self.rows_var.set(rows)
        self.cols_var.set(cols)
        self.mines_var.set(mines)

        self.board = Board(rows=rows, cols=cols, num_mines=mines)
        self._resize_canvas()
        self._update_mines_left()
        self.last_solver_message = ""
        self.draw_board()
        self._game_over_shown = False


    def ai_step(self) -> None:
        """Run one AI step using CSP then probabilistic fallback."""
        if not self.board or self.board.game_over:
            return
        # If nothing is open yet, open center to seed the board safely.
        if not self.board.mines_placed:
            self.board.open_cell(self.board.rows // 2, self.board.cols // 2)

        solver_message = "CSP solver has been used"
        moves = self.csp_solver.play_step(self.board)
        if not moves and not self.board.game_over:
            solver_message = "Probability_Solver has been used"
            self.prob_solver.play_step(self.board)
        self.last_solver_message = solver_message

        if self.board.game_over and not self.board.win:
            self.board.reveal_all_mines()

        self._update_mines_left()
        self.draw_board()
        self._maybe_show_game_over()

    # Event handlers
    def on_left_click(self, event) -> None:
        self._handle_click(event, action="open")

    def on_right_click(self, event) -> None:
        self._handle_click(event, action="flag")

    def _handle_click(self, event, action: str) -> None:
        if not self.board or self.board.game_over:
            return
        row, col = self._coords_from_event(event)
        if row is None:
            return

        try:
            if action == "open":
                self.board.open_cell(row, col)
                if self.board.game_over and not self.board.win:
                    self.board.reveal_all_mines()
            else:
                self.board.flag_cell(row, col)
        except IndexError:
            return

        self._update_mines_left()
        self.draw_board()

        if self.board.game_over:
            msg = "You win! 🎉" if self.board.win else "Boom! You hit a mine."
            self._maybe_show_game_over()


    # Drawing
    def _resize_canvas(self) -> None:
        if not self.board:
            return
        w = self.board.cols * CELL_SIZE + BOARD_BORDER * 2
        h = self.board.rows * CELL_SIZE + BOARD_BORDER * 2
        self.canvas.config(width=w, height=h)

    def draw_board(self) -> None:
        if not self.board:
            return

        self.canvas.delete("all")
        rows, cols = self.board.rows, self.board.cols

        # Outer border
        w = cols * CELL_SIZE + BOARD_BORDER * 2
        h = rows * CELL_SIZE + BOARD_BORDER * 2
        self.canvas.create_rectangle(
            0, 0, w - 1, h - 1, outline="black", fill=CANVAS_BG, width=BOARD_BORDER
        )

        for r in range(rows):
            for c in range(cols):
                cell = self.board.get_cell(r, c)
                x0 = BOARD_BORDER + c * CELL_SIZE
                y0 = BOARD_BORDER + r * CELL_SIZE
                x1 = x0 + CELL_SIZE
                y1 = y0 + CELL_SIZE

                fill = CELL_OPEN if cell.is_open else CELL_CLOSED
                self.canvas.create_rectangle(
                    x0, y0, x1, y1, fill=fill, outline="#7a7a7a", width=1
                )

                if cell.state == CellState.FLAGGED:
                    self.canvas.create_text(
                        (x0 + x1) / 2,
                        (y0 + y1) / 2,
                        text=FLAG_GLYPH,
                        font=("Segoe UI Emoji", 14, "bold"),
                    )
                elif cell.is_open:
                    if cell.is_mine:
                        self.canvas.create_text(
                            (x0 + x1) / 2,
                            (y0 + y1) / 2,
                            text="💣",
                            font=("Segoe UI Emoji", 14, "bold"),
                        )
                    elif cell.adjacent_mines > 0:
                        num = cell.adjacent_mines
                        self.canvas.create_text(
                            (x0 + x1) / 2,
                            (y0 + y1) / 2,
                            text=str(num),
                            fill=NUMBER_COLORS.get(num, "black"),
                            font=("Arial", 12, "bold"),
                        )

        if self.last_solver_message:
            # Small overlay in the bottom-left corner indicating which solver acted last.
            self.canvas.create_text(
                BOARD_BORDER + 6,
                h - BOARD_BORDER - 6,
                text=self.last_solver_message,
                fill="white",
                anchor="sw",
                font=("Arial", 9, "bold"),
            )

    # Helpers
    def _coords_from_event(self, event) -> tuple[int | None, int | None]:
        if not self.board:
            return None, None
        col = (event.x - BOARD_BORDER) // CELL_SIZE
        row = (event.y - BOARD_BORDER) // CELL_SIZE
        if 0 <= row < self.board.rows and 0 <= col < self.board.cols:
            return int(row), int(col)
        return None, None

    def _update_mines_left(self) -> None:
        if not self.board:
            self.mines_left_var.set("Mines left: -")
            return
        self.mines_left_var.set(f"Mines left: {self.board.remaining_mines_estimate()}")


if __name__ == "__main__":
    app = MinesweeperUI()
    app.mainloop()
