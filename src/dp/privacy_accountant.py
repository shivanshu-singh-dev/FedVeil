import math


def compute_epsilon(clip_bound: float, noise_scale: float, delta: float = 1e-5) -> float:
    """
    Computes the epsilon for one round's noise release using the analytic
    Gaussian mechanism formula:
        epsilon = (clip_bound / noise_scale) * sqrt(2 * ln(1.25 / delta))
    """
    return (clip_bound / noise_scale) * math.sqrt(2 * math.log(1.25 / delta))
