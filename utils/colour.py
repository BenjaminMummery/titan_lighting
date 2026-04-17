from utils.maths import clamp
WHITE: tuple[int, int, int] = (255, 255, 255)
RED: tuple[int, int, int] = (255, 0, 0)
ORANGE: tuple[int, int, int] = (255, 40, 0)
GREEN: tuple[int, int, int] = (0, 255, 0)

def colour_at_brightness(colour: tuple[int, int, int], brightness: float) -> tuple[int, int, int]:
    """Return the specified colour scaled to the specific brightness."""
    # TODO: remove any previous scaling - (1, 1, 1) and (255, 255, 255) should give the same result.
    return tuple(int(val*clamp(brightness)) for val in colour)

def add_colours(colour_1: tuple[int, int, int], colour_2: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(min(255, col_1 + col_2) for col_1, col_2 in zip(colour_1, colour_2))