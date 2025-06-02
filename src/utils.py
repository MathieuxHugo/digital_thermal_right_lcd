import numpy as np

def interpolate_color(start_color: str, end_color: str, factor: float) -> str:
    """
    Interpolates between two hex colors.
    Args:
        start_color (str): The starting color in hex format (e.g., '#ff0000').
        end_color (str): The ending color in hex format (e.g., '#00ff00').
        factor (float): A value between 0 and 1 that determines the interpolation factor.
                        0 returns the start color, 1 returns the end color.
    Returns:
        str: The interpolated color in hex format.
    """
    start_color = np.array([int(start_color[i:i+2], 16) for i in (0, 2, 4)])
    end_color = np.array([int(end_color[i:i+2], 16) for i in (0, 2, 4)])
    interpolated_color = (start_color * (1 - factor) + end_color * factor).astype(int)
    return ''.join(f"{c:02x}" for c in interpolated_color)

def get_random_color():
    return (f"{np.random.randint(0, 256):02x}{np.random.randint(0, 256):02x}{np.random.randint(0, 256):02x}")
                