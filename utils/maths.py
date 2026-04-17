def clamp(input: float, min:float = 0, max: float = 1) -> float:
    """Return the input value clamped to be between the min and max."""
    if input<min:
        return min
    elif input > max:
        return max
    return input

def wrap(input: float, min: float = 0, max: float = 1) -> float:
    """Return the input value wrapped to be between the min and max."""
    return input % (max-min) + min