import unittest
import numpy as np
from phe import paillier

from src.server.aggregator import aggregate_ciphertexts


class TestHEPipeline(unittest.TestCase):
    def test_he_pipeline_deterministic_sum(self):
        # 1. Define 3 fixed known plaintext vectors (deterministic, no randomness)
        v1 = [1.5, -2.0, 3.25, 0.5]
        v2 = [0.5, 4.0, -1.25, 2.0]
        v3 = [-1.0, 0.5, 2.0, -1.5]

        # Calculate exact expected sum: [1.0, 2.5, 4.0, 1.0]
        expected_sum = [
            v1[i] + v2[i] + v3[i]
            for i in range(len(v1))
        ]

        # 2. Generate a Paillier keypair
        pub_key, priv_key = paillier.generate_paillier_keypair(n_length=1024)

        # 3. Encrypt each vector with public key
        enc_v1 = [pub_key.encrypt(x) for x in v1]
        enc_v2 = [pub_key.encrypt(x) for x in v2]
        enc_v3 = [pub_key.encrypt(x) for x in v3]

        encrypted_vectors = [enc_v1, enc_v2, enc_v3]

        # 4. Homomorphic aggregation over ciphertexts
        encrypted_sum = aggregate_ciphertexts(encrypted_vectors)

        # 5. Decrypt the aggregated result
        decrypted_sum = [priv_key.decrypt(x) for x in encrypted_sum]

        # 6. Assert decrypted sum exactly matches known sum within floating point tolerance
        self.assertEqual(len(decrypted_sum), len(expected_sum))
        for actual, expected in zip(decrypted_sum, expected_sum):
            self.assertAlmostEqual(actual, expected, places=6)


if __name__ == "__main__":
    unittest.main()
