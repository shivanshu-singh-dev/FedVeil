import numpy as np

def apply_dp_noise(weights, clip_bound=1.0, noise_scale=0.1):
    """Clips the array to bound sensitivity, then adds Gaussian noise."""
    norm = np.linalg.norm(weights)
    if norm > clip_bound:
        weights = weights * (clip_bound / norm)
        
    noise = np.random.normal(loc=0.0, scale=noise_scale, size=len(weights))
    noisy_weights = weights + noise
    
    return noisy_weights