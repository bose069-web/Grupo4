import importlib.util
import io
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch


SOURCE_PATH = Path(__file__).with_name("tres en raya  COPILOT")
LOADER = SourceFileLoader("tic_tac_toe", str(SOURCE_PATH))
SPEC = importlib.util.spec_from_loader("tic_tac_toe", LOADER)
GAME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GAME)


class TestCreateBoard(unittest.TestCase):
    def test_creates_three_by_three_empty_board(self):
        board = GAME.create_board()

        self.assertEqual(board, [[" ", " ", " "] for _ in range(3)])

    def test_rows_are_independent(self):
        board = GAME.create_board()
        board[0][0] = "X"

        self.assertEqual(board[1][0], " ")


class TestPrintBoard(unittest.TestCase):
    def test_prints_rows_and_separators(self):
        output = io.StringIO()
        with patch("sys.stdout", output):
            GAME.print_board(GAME.create_board())

        self.assertEqual(output.getvalue(), "   |   |  \n---------\n" * 3)


class TestHasWon(unittest.TestCase):
    def test_detects_row_column_and_diagonal_wins(self):
        boards = [
            [["X", "X", "X"], ["O", " ", " "], [" ", " ", "O"]],
            [["X", "O", " "], ["X", " ", "O"], ["X", " ", " "]],
            [["X", "O", " "], [" ", "X", "O"], [" ", " ", "X"]],
            [[" ", "O", "X"], [" ", "X", "O"], ["X", " ", " "]],
        ]

        for board in boards:
            with self.subTest(board=board):
                self.assertTrue(GAME.has_won(board, "X"))

    def test_returns_false_without_a_win(self):
        board = [["X", "O", " "], [" ", "X", "O"], ["O", " ", " "]]

        self.assertFalse(GAME.has_won(board, "X"))


class TestIsValidMove(unittest.TestCase):
    def test_accepts_empty_in_bounds_cell(self):
        self.assertTrue(GAME.is_valid_move(GAME.create_board(), 1, 2))

    def test_rejects_occupied_cell(self):
        board = GAME.create_board()
        board[1][2] = "O"

        self.assertFalse(GAME.is_valid_move(board, 1, 2))

    def test_rejects_out_of_bounds_coordinates(self):
        board = GAME.create_board()

        self.assertFalse(GAME.is_valid_move(board, -1, 0))
        self.assertFalse(GAME.is_valid_move(board, 0, 3))


class TestGetMove(unittest.TestCase):
    def test_reads_row_and_column(self):
        with patch("builtins.input", side_effect=["1", "2"]):
            self.assertEqual(GAME.get_move("X"), (1, 2))

    def test_propagates_invalid_number(self):
        with patch("builtins.input", side_effect=["invalid"]):
            with self.assertRaises(ValueError):
                GAME.get_move("O")


class TestSwitchPlayer(unittest.TestCase):
    def test_switches_players(self):
        self.assertEqual(GAME.switch_player("X"), "O")
        self.assertEqual(GAME.switch_player("O"), "X")


class TestPlayTicTacToe(unittest.TestCase):
    def test_returns_true_when_x_wins(self):
        moves = ["0", "0", "1", "0", "0", "1", "2", "2"]
        with patch("builtins.input", side_effect=moves), patch("sys.stdout"):
            result = GAME.play_tic_tac_toe()

        self.assertTrue(result)

    def test_returns_false_on_draw(self):
        moves = ["0", "0", "0", "1", "0", "2", "1", "1", "1", "0", "1", "2", "2", "0", "2", "1", "2", "2"]
        with patch("builtins.input", side_effect=moves), patch("sys.stdout"):
            result = GAME.play_tic_tac_toe()

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()