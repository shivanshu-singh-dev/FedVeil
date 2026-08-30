import os
import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


def main():
    # 1. Ensure data directory exists
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)

    # 2. Load dataset
    raw_data = load_breast_cancer()
    X = raw_data.data
    y = raw_data.target

    # 3. Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 4. Hold out 20% as a fixed test set
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X_scaled, y, test_size=0.20, random_state=42, stratify=y
    )

    server_test_path = os.path.join(data_dir, "server_test.npz")
    np.savez(server_test_path, X=X_test, y=y_test)
    print(f"Saved server test set to {server_test_path} (samples: {len(y_test)}, features: {X_test.shape[1]})")

    # 5. Split the remaining 80% into 3 equal IID shards
    indices = np.arange(len(y_train_val))
    np.random.seed(42)
    np.random.shuffle(indices)

    shard_splits = np.array_split(indices, 3)
    for idx, shard_indices in enumerate(shard_splits, start=1):
        client_X = X_train_val[shard_indices]
        client_y = y_train_val[shard_indices]
        client_path = os.path.join(data_dir, f"client_{idx}.npz")
        np.savez(client_path, X=client_X, y=client_y)
        print(f"Saved client {idx} dataset to {client_path} (samples: {len(client_y)}, features: {client_X.shape[1]})")


if __name__ == "__main__":
    main()
