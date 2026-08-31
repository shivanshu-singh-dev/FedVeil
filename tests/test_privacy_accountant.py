import unittest
from src.dp.privacy_accountant import compute_epsilon


class TestPrivacyAccountant(unittest.TestCase):
    def test_compute_epsilon_default_params(self):
        clip_bound = 1.0
        noise_scale = 0.05
        delta = 1e-5

        eps = compute_epsilon(clip_bound=clip_bound, noise_scale=noise_scale, delta=delta)

        # Check positive sane number
        self.assertIsInstance(eps, float)
        self.assertGreater(eps, 0.0)
        # For clip_bound=1.0, noise_scale=0.05, delta=1e-5:
        # eps = (1.0 / 0.05) * sqrt(2 * ln(1.25 / 1e-5)) ≈ 20 * sqrt(2 * ln(125000)) ≈ 20 * sqrt(2 * 11.736) ≈ 96.89
        self.assertAlmostEqual(eps, 96.896, places=2)

    def test_smaller_noise_scale_produces_larger_epsilon(self):
        clip_bound = 1.0
        delta = 1e-5

        eps_high_noise = compute_epsilon(clip_bound, noise_scale=0.1, delta=delta)
        eps_low_noise = compute_epsilon(clip_bound, noise_scale=0.01, delta=delta)

        # Less noise added implies greater privacy loss (higher epsilon)
        self.assertGreater(eps_low_noise, eps_high_noise)

    def test_larger_clip_bound_produces_larger_epsilon(self):
        noise_scale = 0.05
        delta = 1e-5

        eps_small_clip = compute_epsilon(clip_bound=0.5, noise_scale=noise_scale, delta=delta)
        eps_large_clip = compute_epsilon(clip_bound=2.0, noise_scale=noise_scale, delta=delta)

        self.assertGreater(eps_large_clip, eps_small_clip)


if __name__ == "__main__":
    unittest.main()
