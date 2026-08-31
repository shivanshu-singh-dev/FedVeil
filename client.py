import argparse
import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional
import numpy as np
from phe import paillier

from src.dp.dummy_dp import apply_dp_noise
from src.crypto.serializer import serialize_payload
from src.model.logistic_regression import train_local


def fetch_server_state(server_url: str):
    """Fetches telemetry state including public key and current weights from the coordinator."""
    url = f"{server_url.rstrip('/')}/api/telemetry"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Server returned status {response.status}")
        data = json.loads(response.read().decode("utf-8"))
        return data


def submit_client_update(server_url: str, payload_data: dict):
    """Submits the encrypted payload to the coordinator."""
    url = f"{server_url.rstrip('/')}/api/submit-update"
    req_body = json.dumps(payload_data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_body,
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        resp_data = json.loads(response.read().decode("utf-8"))
        return resp_data


def run_client_round(
    client_id: int | str,
    server_url: str,
    client_data_path: Optional[str] = None,
    target_round: Optional[int] = None,
    clip_bound: float = 1.0,
    noise_scale: float = 0.05,
    epochs: int = 5,
    lr: float = 0.1
):
    """
    Executes one round of local model training, DP noise injection,
    Paillier homomorphic encryption, and transmission to the coordinator.
    """
    # 1. Resolve and load local client dataset
    if client_data_path is None:
        client_data_path = os.path.join("data", f"client_{client_id}.npz")

    if not os.path.exists(client_data_path):
        raise FileNotFoundError(f"Client dataset file not found: {client_data_path}")

    dataset = np.load(client_data_path)
    X, y = dataset["X"], dataset["y"]

    # 2. Fetch server state (public key and current weights)
    server_state = fetch_server_state(server_url)
    active_round = target_round if target_round is not None else server_state.get("current_round", 1)
    pk_n = int(server_state["public_key"]["n"])
    pub_key = paillier.PaillierPublicKey(n=pk_n)

    current_weights = np.array(
        server_state.get("current_weights", np.zeros(X.shape[1] + 1)),
        dtype=float
    )

    print(f"[Client {client_id}] Starting Round {active_round} local training on {len(y)} samples...")
    t0 = time.time()

    # 3. Local training: full-batch gradient descent
    trained_weights = train_local(X, y, current_weights, epochs=epochs, lr=lr)
    raw_delta = trained_weights - current_weights

    # 4. Apply Differential Privacy noise
    noisy_delta = apply_dp_noise(raw_delta, clip_bound=clip_bound, noise_scale=noise_scale)

    # 5. Encrypt delta with Paillier Homomorphic Encryption
    encrypted_delta = [pub_key.encrypt(float(x)) for x in noisy_delta]

    # 6. Serialize payload
    serialized_payload = serialize_payload(pub_key, encrypted_delta)

    compute_duration_ms = round((time.time() - t0) * 1000, 2)
    print(f"[Client {client_id}] Training & encryption completed in {compute_duration_ms} ms. Submitting payload...")

    # 7. Post update to coordinator
    submission_data = {
        "client_id": client_id,
        "round": active_round,
        "payload": serialized_payload,
        "clip_bound": clip_bound,
        "noise_scale": noise_scale,
        "raw_slice_preview": [float(x) for x in noisy_delta[:4]],
        "compute_ms": compute_duration_ms
    }

    resp = submit_client_update(server_url, submission_data)
    print(f"[Client {client_id}] Server response: {resp}")
    return resp


def main():
    parser = argparse.ArgumentParser(description="FedVeil Standalone Federated Client")
    parser.add_argument("--id", type=str, default="1", help="Client identifier (default: 1)")
    parser.add_argument("--server", type=str, default="http://127.0.0.1:8000", help="Coordinator URL")
    parser.add_argument("--client-data", type=str, default=None, help="Path to client .npz data (default: data/client_{id}.npz)")
    parser.add_argument("--epochs", type=int, default=5, help="Local training epochs (default: 5)")
    parser.add_argument("--lr", type=float, default=0.1, help="Learning rate (default: 0.1)")
    parser.add_argument("--clip-bound", type=float, default=1.0, help="DP clipping bound (default: 1.0)")
    parser.add_argument("--noise-scale", type=float, default=0.05, help="DP Gaussian noise scale (default: 0.05)")
    parser.add_argument("--round", type=int, default=None, help="Explicit round number to submit for")
    parser.add_argument("--loop", action="store_true", help="Continuously participate across rounds until completed")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds when looping")

    args = parser.parse_args()

    client_data = args.client_data or os.path.join("data", f"client_{args.id}.npz")

    if not args.loop:
        run_client_round(
            client_id=args.id,
            server_url=args.server,
            client_data_path=client_data,
            target_round=args.round,
            clip_bound=args.clip_bound,
            noise_scale=args.noise_scale,
            epochs=args.epochs,
            lr=args.lr
        )
    else:
        print(f"[Client {args.id}] Starting loop mode against {args.server} (data: {client_data})...")
        last_participated_round = 0
        while True:
            try:
                state = fetch_server_state(args.server)
                current_round = state.get("current_round", 1)
                status = state.get("status", "idle")

                if status == "completed":
                    print(f"[Client {args.id}] Coordinator marked training as completed. Exiting.")
                    break

                if current_round > last_participated_round and status in ("waiting_for_updates", "running", "idle"):
                    run_client_round(
                        client_id=args.id,
                        server_url=args.server,
                        client_data_path=client_data,
                        target_round=current_round,
                        clip_bound=args.clip_bound,
                        noise_scale=args.noise_scale,
                        epochs=args.epochs,
                        lr=args.lr
                    )
                    last_participated_round = current_round

                time.sleep(args.interval)
            except KeyboardInterrupt:
                print(f"\n[Client {args.id}] Stopped by user.")
                break
            except Exception as e:
                print(f"[Client {args.id}] Error: {e}. Retrying in {args.interval}s...")
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
