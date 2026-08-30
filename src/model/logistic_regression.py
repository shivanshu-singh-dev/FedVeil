import numpy as np


def predict(X: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """
    Computes predicted probabilities for input features X.
    weights is a flat 1D array of size (n_features + 1), where weights[-1] is the bias.
    """
    X = np.asarray(X)
    weights = np.asarray(weights, dtype=float)
    w = weights[:-1]
    b = weights[-1]

    z = np.dot(X, w) + b
    # Clip z to prevent numerical overflow in exp
    z = np.clip(z, -500.0, 500.0)
    probs = 1.0 / (1.0 + np.exp(-z))
    return probs


def train_local(
    X: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    epochs: int = 5,
    lr: float = 0.1
) -> np.ndarray:
    """
    Performs full-batch gradient descent for logistic regression starting from weights.
    Returns the updated weights of the same shape (n_features + 1,).
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    weights = np.asarray(weights, dtype=float)

    w = np.copy(weights[:-1])
    b = float(weights[-1])
    n_samples = X.shape[0]

    for _ in range(epochs):
        z = np.dot(X, w) + b
        z = np.clip(z, -500.0, 500.0)
        probs = 1.0 / (1.0 + np.exp(-z))

        error = probs - y
        grad_w = np.dot(X.T, error) / n_samples
        grad_b = np.sum(error) / n_samples

        w -= lr * grad_w
        b -= lr * grad_b

    return np.append(w, b)


def evaluate(X: np.ndarray, y: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    """
    Evaluates the model on test dataset (X, y).
    Returns (accuracy_percentage, log_loss) as plain floats.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)

    probs = predict(X, weights)
    preds = (probs >= 0.5).astype(int)

    accuracy = float(np.mean(preds == y) * 100.0)

    # Compute binary cross-entropy / log loss with clipping for stability
    eps = 1e-15
    probs_clipped = np.clip(probs, eps, 1.0 - eps)
    loss = float(-np.mean(y * np.log(probs_clipped) + (1.0 - y) * np.log(1.0 - probs_clipped)))

    return accuracy, loss
