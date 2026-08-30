# FedVeil: Privacy-Preserving Federated Learning Engine

FedVeil is a secure federated learning orchestration framework that combines **Paillier Homomorphic Encryption (HE)** and **Differential Privacy (DP)** to train machine learning models across decentralized nodes without exposing raw data or allowing server-side gradient reconstruction.

---

## Architecture & Responsibilities

### Phase 1: Cryptographic Core & Telemetry Dashboard (Current)
* **`src/crypto/serializer.py`**: Handles Paillier public-private key serialization so encrypted vectors can be transmitted as JSON payloads.
* **`src/dp/dummy_dp.py`**: Applies differential privacy noise scaling and sensitivity clipping to simulated weight updates.
* **`src/server/aggregator.py`**: Performs blind homomorphic summation across client ciphertexts without requiring the private decryption key.
* **`src/api/server.py`**: FastAPI telemetry engine managing round states, privacy budgeting ($\epsilon$), and inference endpoints.
* **`frontend/`**: Lightweight React dashboard for monitoring active nodes, convergence metrics, and testing model inference.

### Phase 2: Cloud Ingestion & Scaling (Handoff)
* **Amazon S3**: Scalable object storage drop-box for bulky Paillier ciphertext blobs.
* **Amazon RDS / MySQL**: Relational metadata database tracking client submission states, rounds, and timestamps.
* **AWS EC2 / Nginx**: Cloud server hosting the asynchronous aggregation worker and routing API endpoints.

---

## Quick Start Guide

### 1. Python Backend Setup
Create and activate a virtual environment, then install the required dependencies:
```powershell
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt

```

### 2. Run the FastAPI Backend
Ensure your Python virtual environment is activated, then start the server:
```powershell
python -m uvicorn src.api.server:app --reload --port 8000
```

### 3. Run the React Frontend
Open a second terminal, navigate to the frontend directory, and launch Vite:
```powershell
cd frontend
npm run dev
```