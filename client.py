import argparse
import json
import time
import urllib.request
import urllib.error
import numpy as np
from phe import paillier

from src.dp.dummy_dp import apply_dp_noise
from src.crypto.serializer import serialize_payload


def fetch_server_state(server_url: str):
    """Fetches public key and current round from the coordinator."""
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
    target_round: int = None,
    vector_size: int = 4,
    clip_bound: float = 1.0,
    noise_scale: float = 0.05
):
    """
    Executes one round of local data placeholder generation, DP noise injection,
    Paillier homomorphic encryption, and transmission to the coordinator.
    """
    # 1. Fetch server state / public key
    server_state = fetch_server_state(server_url)
    active_round = target_round if target_round is not None else server_state.get("current_round", 1)
    pk_n = int(server_state["public_key"]["n"])
    pub_key = paillier.PaillierPublicKey(n=pk_n)

    print(f"[Client {client_id}] Starting Round {active_round} computation...")
    t0 = time.time()

    # 2. Generate local data placeholder
    raw_delta = np.random.uniform(-0.4, 0.4, size=vector_size)

    # 3. Apply Differential Privacy noise
    noisy_delta = apply_dp_noise(raw_delta, clip_bound=clip_bound, noise_scale=noise_scale)

    # 4. Encrypt with Paillier Homomorphic Encryption
    encrypted_delta = [pub_key.encrypt(float(x)) for x in noisy_delta]

    # 5. Serialize payload
    serialized_payload = serialize_payload(pub_key, encrypted_delta)

    compute_duration_ms = round((time.time() - t0) * 1000, 2)
    print(f"[Client {client_id}] Encryption completed in {compute_duration_ms} ms. Submitting payload...")

    # 6. Post update to coordinator
    submission_data = {
        "client_id": client_id,
        "round": active_round,
        "payload": serialized_payload,
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
    parser.add_argument("--vector-size", type=int, default=4, help="Model vector dimension (default: 4)")
    parser.add_argument("--clip-bound", type=float, default=1.0, help="DP clipping bound (default: 1.0)")
    parser.add_argument("--noise-scale", type=float, default=0.05, help="DP Gaussian noise scale (default: 0.05)")
    parser.add_argument("--round", type=int, default=None, help="Explicit round number to submit for")
    parser.add_argument("--loop", action="store_true", help="Continuously participate across rounds until completed")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds when looping")

    args = parser.parse_args()

    if not args.loop:
        run_client_round(
            client_id=args.id,
            server_url=args.server,
            target_round=args.round,
            vector_size=args.vector_size,
            clip_bound=args.clip_bound,
            noise_scale=args.noise_scale
        )
    else:
        print(f"[Client {args.id}] Starting loop mode against {args.server}...")
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
                        target_round=current_round,
                        vector_size=args.vector_size,
                        clip_bound=args.clip_bound,
                        noise_scale=args.noise_scale
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
