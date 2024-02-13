from dataclasses import dataclass
from typing import Tuple


@dataclass
class Pos:
    """A position in source file that consists of a starting and ending point, both inclusive.
    Each point is a zero-based coordinate (row, offset in row)."""
    start: Tuple[int, int]
    end: Tuple[int, int]
