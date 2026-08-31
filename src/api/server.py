import os
import time
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from phe import paillier
from src.crypto.serializer import serialize_payload, deserialize_payload
from src.server.aggregator import aggregate_ciphertexts
from src.model.logistic_regression import evaluate
from src.dp.privacy_accountant import compute_epsilon
from src.storage.privacy_log_db import log_epsilon, get_cumulative_epsilon, get_all_privacy_logs

app = FastAPI(title="FedVeil Coordinator Engine", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load test dataset for model evaluation on server
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DATA_PATH = os.path.join(BASE_DIR, "data", "server_test.npz")

if os.path.exists(TEST_DATA_PATH):
    test_data = np.load(TEST_DATA_PATH)
    X_test, y_test = test_data["X"], test_data["y"]
    VECTOR_SIZE = X_test.shape[1] + 1  # n_features + bias
else:
    X_test, y_test = None, None
    VECTOR_SIZE = 31

# Key custody: coordinator holds Paillier keypair
pub_key, priv_key = paillier.generate_paillier_keypair(n_length=1024)

# Global weights initialization
current_weights = np.zeros(VECTOR_SIZE)

# Submissions buffer for current active round: {client_id: UpdateSubmission}
current_round_submissions: Dict[str, Any] = {}

# In-memory store for frontend and client telemetry
telemetry_store: Dict[str, Any] = {
    "status": "waiting_for_updates",
    "total_rounds": 5,
    "current_round": 1,
    "expected_clients": 3,
    "epsilon_note": "See /api/privacy-log for real per-client epsilon values",
    "current_weights": [round(float(w), 4) for w in current_weights],
    "rounds_data": [],
    "clients_status": [
        {"id": i, "name": f"Client Node {i}", "status": "Ready", "last_latency_ms": 0.0}
        for i in range(1, 4)
    ],
    "sample_payload_inspect": {
        "raw_slice": [],
        "ciphertext_preview": ""
    },
    "public_key": {
        "n": str(pub_key.n)
    }
}


class UpdateSubmission(BaseModel):
    client_id: Any
    round: int
    payload: str
    clip_bound: Optional[float] = 1.0
    noise_scale: Optional[float] = 0.05
    delta: Optional[float] = 1e-5
    raw_slice_preview: Optional[List[float]] = None
    compute_ms: Optional[float] = None


class CoordinatorConfigRequest(BaseModel):
    num_clients: int = 3
    num_rounds: int = 5
    vector_size: int = VECTOR_SIZE


@app.get("/api/telemetry")
def get_telemetry():
    """Returns current telemetry state for frontend monitoring and clients."""
    return telemetry_store


@app.get("/api/public-key")
def get_public_key():
    """Returns the coordinator Paillier public key for client encryption."""
    return {
        "public_key": {
            "n": str(pub_key.n)
        },
        "current_round": telemetry_store["current_round"],
        "status": telemetry_store["status"]
    }


@app.get("/api/privacy-log")
def get_privacy_log():
    """Returns all rows from the privacy_log table as JSON, most recent first."""
    return get_all_privacy_logs()


@app.post("/api/submit-update")
def submit_update(submission: UpdateSubmission):
    """
    Accepts one client's serialized encrypted payload for the current round.
    Once submissions from expected clients are received, aggregates, decrypts,
    persists per-client privacy accounting, updates telemetry_store, evaluates
    the real model, and advances the round.
    """
    global current_weights, current_round_submissions, telemetry_store

    active_round = telemetry_store["current_round"]

    if submission.round != active_round:
        raise HTTPException(
            status_code=400,
            detail=f"Submission round {submission.round} does not match active round {active_round}"
        )

    cid_str = str(submission.client_id)
    current_round_submissions[cid_str] = submission

    # Update or add client in clients_status
    client_entry = next((c for c in telemetry_store["clients_status"] if str(c["id"]) == cid_str), None)
    if client_entry:
        client_entry["status"] = "Update Received"
        if submission.compute_ms is not None:
            client_entry["last_latency_ms"] = round(submission.compute_ms, 2)
    else:
        telemetry_store["clients_status"].append({
            "id": submission.client_id,
            "name": f"Client Node {submission.client_id}",
            "status": "Update Received",
            "last_latency_ms": round(submission.compute_ms or 0.0, 2)
        })

    # Update frontend sample preview if on round 1
    if active_round == 1:
        if submission.raw_slice_preview:
            telemetry_store["sample_payload_inspect"]["raw_slice"] = [
                round(float(x), 4) for x in submission.raw_slice_preview[:4]
            ]
        if submission.payload:
            telemetry_store["sample_payload_inspect"]["ciphertext_preview"] = (
                submission.payload[:160] + " ... [TRUNCATED]"
            )

    received_count = len(current_round_submissions)
    expected_count = telemetry_store["expected_clients"]

    # If all expected clients have submitted, aggregate and advance round
    if received_count >= expected_count:
        t0_agg = time.time()

        # Deserialization & HE Aggregation
        deserialized_vectors = [
            deserialize_payload(sub.payload)[1]
            for sub in current_round_submissions.values()
        ]
        encrypted_sum = aggregate_ciphertexts(deserialized_vectors)
        agg_ms = round((time.time() - t0_agg) * 1000, 2)

        # Decryption & Global Weights Update
        decrypted_sum = np.array([priv_key.decrypt(x) for x in encrypted_sum])
        averaged_delta = decrypted_sum / expected_count
        current_weights = current_weights + averaged_delta
        telemetry_store["current_weights"] = [round(float(w), 4) for w in current_weights]

        # Real test set evaluation
        if X_test is not None and y_test is not None:
            acc, loss = evaluate(X_test, y_test, current_weights)
            real_acc = round(acc, 2)
            real_loss = round(loss, 4)
        else:
            real_acc = None
            real_loss = None

        # Real Privacy Accounting per client -> SQLite log
        for cid, sub in current_round_submissions.items():
            clip_b = sub.clip_bound if sub.clip_bound is not None else 1.0
            noise_s = sub.noise_scale if sub.noise_scale is not None else 0.05
            delta_val = sub.delta if sub.delta is not None else 1e-5

            eps_round = compute_epsilon(clip_b, noise_s, delta_val)
            prior_cum_eps = get_cumulative_epsilon(cid)
            new_cum_eps = prior_cum_eps + eps_round

            log_epsilon(
                client_id=cid,
                round=active_round,
                epsilon_this_round=eps_round,
                cumulative_epsilon=new_cum_eps,
                clip_bound=clip_b,
                noise_scale=noise_s,
                delta=delta_val
            )

        # Record telemetry metrics for the completed round
        telemetry_store["rounds_data"].append({
            "round": active_round,
            "accuracy": real_acc,
            "loss": real_loss,
            "server_agg_ms": agg_ms,
            "global_weights": [round(float(w), 4) for w in current_weights]
        })

        # Advance round or mark completed
        current_round_submissions.clear()
        if active_round >= telemetry_store["total_rounds"]:
            telemetry_store["status"] = "completed"
            for c in telemetry_store["clients_status"]:
                c["status"] = "Synced & Idle"
        else:
            telemetry_store["current_round"] = active_round + 1
            telemetry_store["status"] = "waiting_for_updates"
            for c in telemetry_store["clients_status"]:
                c["status"] = "Waiting for Round Update"

        return {
            "status": "aggregated",
            "completed_round": active_round,
            "current_round": telemetry_store["current_round"],
            "agg_ms": agg_ms,
            "accuracy": real_acc,
            "loss": real_loss
        }

    return {
        "status": "accepted",
        "round": active_round,
        "received": received_count,
        "expected": expected_count
    }


@app.post("/api/run-simulation")
def configure_simulation(params: CoordinatorConfigRequest):
    """
    Resets/configures the coordinator session parameters without generating client data.
    Clients must submit updates independently via POST /api/submit-update.
    """
    global current_weights, current_round_submissions, telemetry_store

    current_round_submissions.clear()
    current_weights = np.zeros(VECTOR_SIZE)

    telemetry_store["status"] = "waiting_for_updates"
    telemetry_store["total_rounds"] = params.num_rounds
    telemetry_store["current_round"] = 1
    telemetry_store["expected_clients"] = params.num_clients
    telemetry_store["epsilon_note"] = "See /api/privacy-log for real per-client epsilon values"
    telemetry_store["current_weights"] = [round(float(w), 4) for w in current_weights]
    telemetry_store["rounds_data"] = []
    telemetry_store["clients_status"] = [
        {"id": i, "name": f"Client Node {i}", "status": "Waiting for Round Update", "last_latency_ms": 0.0}
        for i in range(1, params.num_clients + 1)
    ]
    telemetry_store["sample_payload_inspect"] = {
        "raw_slice": [],
        "ciphertext_preview": ""
    }

    return {
        "status": "configured",
        "config": params,
        "current_round": 1
    }


@app.post("/api/predict")
def predict_sample(payload: Dict[str, Any]):
    """Inference endpoint for the frontend demo sandbox."""
    features = payload.get("features", [0.5, 0.2, -0.1, 0.8])
    score = float(1 / (1 + np.exp(-np.sum(features))))
    label = "Positive / High Probability" if score > 0.5 else "Negative / Normal"
    return {
        "prediction": label,
        "confidence": round(score if score > 0.5 else 1 - score, 4),
        "features_processed": len(features)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="127.0.0.1", port=8000, reload=True)