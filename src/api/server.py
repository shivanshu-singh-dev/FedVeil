import time
import numpy as np
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from phe import paillier
from src.dp.dummy_dp import apply_dp_noise
from src.crypto.serializer import serialize_payload, deserialize_payload
from src.server.aggregator import aggregate_ciphertexts

app = FastAPI(title="FedVeil Telemetry Engine", version="1.0.0")

# Enable CORS for React frontend (Vite default port 5173 / React port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for frontend telemetry
telemetry_store: Dict[str, Any] = {
    "status": "idle",
    "total_rounds": 0,
    "current_round": 0,
    "cumulative_epsilon": 0.0,
    "rounds_data": [],
    "clients_status": [],
    "sample_payload_inspect": {
        "raw_slice": [],
        "ciphertext_preview": ""
    }
}

class SimulationRequest(BaseModel):
    num_clients: int = 5
    num_rounds: int = 5
    noise_scale: float = 0.05
    vector_size: int = 4

def run_federated_loop(params: SimulationRequest):
    global telemetry_store
    telemetry_store["status"] = "running"
    telemetry_store["total_rounds"] = params.num_rounds
    telemetry_store["current_round"] = 0
    telemetry_store["cumulative_epsilon"] = 0.0
    telemetry_store["rounds_data"] = []
    
    # Initialize Clients
    telemetry_store["clients_status"] = [
        {"id": i, "name": f"Client Node {i}", "status": "Ready", "last_latency_ms": 0.0}
        for i in range(1, params.num_clients + 1)
    ]

    # Paillier Key Generation
    pub_key, priv_key = paillier.generate_paillier_keypair(n_length=1024)
    current_weights = np.array([0.5, -0.2, 1.0, 0.8][:params.vector_size])
    if len(current_weights) < params.vector_size:
        current_weights = np.pad(current_weights, (0, params.vector_size - len(current_weights)), constant_values=0.5)

    cum_eps = 0.0

    for r in range(1, params.num_rounds + 1):
        telemetry_store["current_round"] = r
        cum_eps += 0.25
        telemetry_store["cumulative_epsilon"] = round(cum_eps, 3)

        staged_payloads = []
        plain_noisy_updates = []
        client_latencies = []

        # 1. Simulate Local Training, DP Noise, & Homomorphic Encryption
        t0_client = time.time()
        for idx, client in enumerate(telemetry_store["clients_status"]):
            client["status"] = "Training & Encrypting"
            c_start = time.time()

            raw_delta = np.random.uniform(-0.4, 0.4, size=params.vector_size)
            noisy_delta = apply_dp_noise(raw_delta, clip_bound=1.0, noise_scale=params.noise_scale)
            plain_noisy_updates.append(noisy_delta)

            encrypted_delta = [pub_key.encrypt(float(x)) for x in noisy_delta]
            payload = serialize_payload(pub_key, encrypted_delta)
            staged_payloads.append(payload)

            c_dur = round((time.time() - c_start) * 1000, 2)
            client["last_latency_ms"] = c_dur
            client["status"] = "Staged to S3"

        client_total_ms = round((time.time() - t0_client) * 1000, 2)

        # Update Sample Ciphertext Inspector for Frontend
        if r == 1 and staged_payloads:
            telemetry_store["sample_payload_inspect"] = {
                "raw_slice": [round(float(x), 4) for x in plain_noisy_updates[0][:4]],
                "ciphertext_preview": staged_payloads[0][:160] + " ... [TRUNCATED]"
            }

        # 2. Cloud Server Aggregation (Additive HE over Ciphertexts)
        t0_agg = time.time()
        deserialized_vectors = [deserialize_payload(p)[1] for p in staged_payloads]
        encrypted_sum = aggregate_ciphertexts(deserialized_vectors)
        agg_ms = round((time.time() - t0_agg) * 1000, 2)

        # 3. Decryption & Global Weights Update
        decrypted_sum = np.array([priv_key.decrypt(x) for x in encrypted_sum])
        averaged_delta = decrypted_sum / params.num_clients
        current_weights = current_weights + averaged_delta

        # Record metrics for charting
        simulated_loss = max(0.12, 1.80 * np.exp(-0.35 * r) + np.random.normal(0, 0.015))
        simulated_acc = min(96.8, 62.0 + (34.0 * (1 - np.exp(-0.30 * r))) + np.random.normal(0, 0.4))

        telemetry_store["rounds_data"].append({
            "round": r,
            "accuracy": round(float(simulated_acc), 2),
            "loss": round(float(simulated_loss), 4),
            "epsilon_spent": round(cum_eps, 2),
            "client_compute_ms": client_total_ms,
            "server_agg_ms": agg_ms,
            "global_weights": [round(float(w), 4) for w in current_weights]
        })

        time.sleep(0.6)  # Small pacing interval for smooth real-time frontend visualization

    for client in telemetry_store["clients_status"]:
        client["status"] = "Synced & Idle"

    telemetry_store["status"] = "completed"

@app.get("/api/telemetry")
def get_telemetry():
    return telemetry_store

@app.post("/api/run-simulation")
def start_simulation(params: SimulationRequest, background_tasks: BackgroundTasks):
    if telemetry_store["status"] == "running":
        return {"status": "error", "message": "Simulation already running"}
    
    background_tasks.add_task(run_federated_loop, params)
    return {"status": "started", "config": params}

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
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)