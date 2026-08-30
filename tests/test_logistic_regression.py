import unittest
import numpy as np
from src.model.logistic_regression import predict, train_local, evaluate


class TestLogisticRegression(unittest.TestCase):
    def test_predict_shape_and_bounds(self):
        X = np.random.randn(20, 5)
        weights = np.random.randn(6)
        probs = predict(X, weights)

        self.assertEqual(probs.shape, (20,))
        self.assertTrue(np.all(probs >= 0.0))
        self.assertTrue(np.all(probs <= 1.0))

    def test_train_local_reduces_loss(self):
        np.random.seed(42)
        # Linearly separable 2D data
        X = np.array([
            [-2.0, -2.0],
            [-1.5, -1.0],
            [1.5, 1.0],
            [2.0, 2.0]
        ])
        y = np.array([0, 0, 1, 1])

        initial_weights = np.zeros(3)
        acc_init, loss_init = evaluate(X, y, initial_weights)

        trained_weights = train_local(X, y, initial_weights, epochs=50, lr=0.5)
        acc_after, loss_after = evaluate(X, y, trained_weights)

        self.assertLess(loss_after, loss_init)
        self.assertEqual(acc_after, 100.0)


if __name__ == "__main__":
    unittest.main()
