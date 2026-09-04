import os
import time
import secrets
import datetime
import numpy as np
import jwt
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from phe import paillier
from src.crypto.serializer import serialize_payload, deserialize_payload
from src.server.aggregator import aggregate_ciphertexts
from src.model.logistic_regression import evaluate
from src.dp.privacy_accountant import compute_epsilon
from src.storage.db_connection import init_tables, get_connection
from src.storage.privacy_log_db import log_epsilon, get_cumulative_epsilon, get_all_privacy_logs
from src.storage.client_registry_db import register_client, is_valid_client, list_clients
from src.storage.rounds_db import log_round, get_latest_round
from src.storage.admin_db import verify_admin_credentials

# ── JWT secret — required at startup ────────────────────────────────────────
_jwt_secret = os.environ.get("JWT_SECRET")
if not _jwt_secret:
    raise RuntimeError(
        "Missing required environment variable: JWT_SECRET. "
        "Set this to a long random string before starting the server."
    )
JWT_SECRET: str = _jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 12

# ── Initialize database tables in RDS Postgres on startup ───────────────────
init_tables()

app = FastAPI(title="FedVeil Coordinator Engine", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Bearer token auth dependency ─────────────────────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)


def verify_admin_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
):
    """
    Validates the Authorization: Bearer <token> header.
    Raises 401 if the token is missing, expired, or has an invalid signature.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Bearer token required."
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Unauthorized: Token has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid token.")
    return payload


# ── Load test dataset for model evaluation on server ────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DATA_PATH = os.path.join(BASE_DIR, "data", "server_test.npz")

if os.path.exists(TEST_DATA_PATH):
    test_data = np.load(TEST_DATA_PATH)
    X_test, y_test = test_data["X"], test_data["y"]
    VECTOR_SIZE = X_test.shape[1] + 1  # n_features + bias
else:
    X_test, y_test = None, None
    VECTOR_SIZE = 31

# ── Key custody: coordinator holds Paillier keypair ──────────────────────────
pub_key, priv_key = paillier.generate_paillier_keypair(n_length=1024)

# ── Restore persisted state from RDS on startup ──────────────────────────────
_latest_round = get_latest_round()
if _latest_round is not None:
    current_weights = np.array(_latest_round["global_weights"], dtype=float)
    _restored_round = _latest_round["round"] + 1
else:
    current_weights = np.zeros(VECTOR_SIZE)
    _restored_round = 0  # Starts at 0 when no prior rounds exist

# Submissions buffer for current active round: {client_id: UpdateSubmission}
current_round_submissions: Dict[str, Any] = {}

# In-memory store for frontend and client telemetry
telemetry_store: Dict[str, Any] = {
    "status": "waiting_for_updates",
    "total_rounds": 5,
    "current_round": _restored_round,
    "expected_clients": 3,
    "epsilon_note": "See /api/privacy-log for real per-client epsilon values",
    "current_weights": [round(float(w), 4) for w in current_weights],
    "rounds_data": [],
    "clients_status": [],
    "sample_payload_inspect": {
        "raw_slice": [],
        "ciphertext_preview": ""
    },
    "public_key": {
        "n": str(pub_key.n)
    }
}


# ── Pydantic models ──────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class RegisterClientRequest(BaseModel):
    client_id: str
    name: str


class UpdateSubmission(BaseModel):
    client_id: Any
    api_key: str
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


# ── Routes ───────────────────────────────────────────────────────────────────

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


@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest):
    """
    Authenticates an admin and returns a signed JWT on success.
    Returns 401 on wrong credentials.
    """
    if not verify_admin_credentials(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=JWT_EXPIRE_HOURS)
    token_payload = {
        "sub": req.username,
        "exp": expire
    }
    token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"token": token}


@app.post("/api/admin/register-client")
def admin_register_client(
    req: RegisterClientRequest,
    _token: dict = Depends(verify_admin_token)
):
    """Admin endpoint to register a new client and generate its API key."""
    try:
        api_key = register_client(client_id=req.client_id, name=req.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "status": "registered",
        "client_id": req.client_id,
        "name": req.name,
        "api_key": api_key
    }


@app.get("/api/admin/clients")
def admin_get_clients(_token: dict = Depends(verify_admin_token)):
    """Admin endpoint to list all registered clients with cumulative epsilon totals."""
    clients = list_clients()
    for c in clients:
        c["cumulative_epsilon"] = get_cumulative_epsilon(c["client_id"])
    return {"clients": clients}


@app.delete("/api/admin/reset")
def admin_reset_database(_token: dict = Depends(verify_admin_token)):
    """Wipes all clients, rounds, and privacy logs, and resets memory state."""
    global current_weights, current_round_submissions, telemetry_store
    
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM privacy_log;")
                cur.execute("DELETE FROM clients;")
                cur.execute("DELETE FROM rounds;")
    finally:
        conn.close()

    # Reset in-memory states completely (Round resets to 0)
    current_round_submissions.clear()
    current_weights = np.zeros(VECTOR_SIZE)
    telemetry_store["status"] = "waiting_for_updates"
    telemetry_store["current_round"] = 0
    telemetry_store["current_weights"] = [0.0] * VECTOR_SIZE
    telemetry_store["rounds_data"] = []
    telemetry_store["clients_status"] = []

    return {"status": "reset_successful", "message": "All database records and session states wiped."}

@app.delete("/api/admin/reset-rounds")
def admin_reset_rounds(_token: dict = Depends(verify_admin_token)):
    """Wipes only rounds and privacy logs, keeps registered clients intact."""
    global current_weights, current_round_submissions, telemetry_store
    
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM privacy_log;")
                cur.execute("DELETE FROM rounds;")
    finally:
        conn.close()

    # Reset in-memory states for training rounds (starts at 0)
    current_round_submissions.clear()
    current_weights = np.zeros(VECTOR_SIZE)
    telemetry_store["status"] = "waiting_for_updates"
    telemetry_store["current_round"] = 0
    telemetry_store["current_weights"] = [0.0] * VECTOR_SIZE
    telemetry_store["rounds_data"] = []
    
    for c in telemetry_store["clients_status"]:
        c["status"] = "Idle"

    return {"status": "success", "message": "Training rounds reset to 0."}

@app.post("/api/submit-update")
def submit_update(submission: UpdateSubmission):
    global current_weights, current_round_submissions, telemetry_store

    if not is_valid_client(submission.client_id, submission.api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or unregistered client credentials."
        )

    active_round = telemetry_store["current_round"]

    if submission.round != active_round:
        raise HTTPException(
            status_code=400,
            detail=f"Submission round {submission.round} does not match active round {active_round}"
        )

    cid_str = str(submission.client_id)
    is_resubmission = cid_str in current_round_submissions
    current_round_submissions[cid_str] = submission

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

    received_count = len(current_round_submissions)
    expected_count = telemetry_store["expected_clients"]

    if received_count >= expected_count:
        t0_agg = time.time()

        deserialized_vectors = [
            deserialize_payload(sub.payload)[1]
            for sub in current_round_submissions.values()
        ]
        encrypted_sum = aggregate_ciphertexts(deserialized_vectors)
        agg_ms = round((time.time() - t0_agg) * 1000, 2)

        decrypted_sum = np.array([priv_key.decrypt(x) for x in encrypted_sum])
        averaged_delta = decrypted_sum / expected_count
        current_weights = current_weights + averaged_delta
        telemetry_store["current_weights"] = [round(float(w), 4) for w in current_weights]

        if X_test is not None and y_test is not None:
            acc, loss = evaluate(X_test, y_test, current_weights)
            real_acc = round(acc, 2)
            real_loss = round(loss, 4)
        else:
            real_acc = None
            real_loss = None

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

        log_round(
            round=active_round,
            global_weights=[float(w) for w in current_weights],
            accuracy=real_acc,
            loss=real_loss,
            agg_ms=agg_ms
        )

        telemetry_store["rounds_data"].append({
            "round": active_round,
            "accuracy": real_acc,
            "loss": real_loss,
            "server_agg_ms": agg_ms,
            "global_weights": [round(float(w), 4) for w in current_weights]
        })

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
            "loss": real_loss,
            "current_weights": telemetry_store["current_weights"],
            "replaced_previous_submission": is_resubmission
        }

    return {
        "status": "accepted",
        "round": active_round,
        "received": received_count,
        "expected": expected_count,
        "current_weights": telemetry_store["current_weights"],
        "replaced_previous_submission": is_resubmission
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="127.0.0.1", port=8000, reload=True)