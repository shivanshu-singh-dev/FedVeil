# FedVeil

FedVeil is an academic prototype for federated learning across simulated clients, using Paillier homomorphic encryption for secure aggregation and Gaussian-noise differential privacy. It includes AWS RDS Postgres-backed persistence for round history, global weights, client registry, and privacy accounting, with JWT-based admin authentication and API-key-based client authentication.

---

## What This Does

- **Real local model training**: Implements full-batch gradient descent for logistic regression on real partitioned data (the Breast Cancer Wisconsin diagnostic dataset), rather than random placeholder vectors.
- **Real Paillier homomorphic encryption**: Clients encrypt parameter updates locally with the coordinator's public key; the coordinator sums the encrypted ciphertexts homomorphically without decrypting individual client updates.
- **Real differential privacy**: Applies Gaussian perturbation to local weight updates prior to encryption, with privacy budget ($\varepsilon$) computed using the analytic Gaussian mechanism formula rather than fixed placeholder values.
- **Persistent RDS Postgres storage**: Persists state across four database tables in AWS RDS Postgres:
  - `rounds`: Stores round history, global model weights (as JSONB), test accuracy, loss, and aggregation latency.
  - `privacy_log`: Logs per-client, per-round $\varepsilon$ expenditures with UTC timestamps.
  - `clients`: Tracks registered clients and their generated API keys.
  - `admins`: Stores admin usernames and bcrypt password hashes.
- **Model state restore**: Restores the latest global weights and current round number from the database on coordinator startup.
- **JWT-based admin authentication**: Protects administrative endpoints using bcrypt password verification, a login endpoint issuing signed JSON Web Tokens (JWTs), and Bearer token authorization.
- **Client authentication**: Requires clients to be pre-registered via the admin API and provide a valid 16-byte hex API key with each submission before updates are accepted.
- **Monitoring dashboard**: Includes a React frontend for monitoring active rounds, aggregation overhead, and test set performance.

---

## Known Limitations

- **Centralized key custody**: The coordinator generates and holds both the Paillier public and private keys, decrypting the aggregate directly. Because threshold or multi-party decryption is not implemented, a compromised coordinator could decrypt individual client ciphertexts before aggregation.
- **No MPC masking**: Homomorphic encryption is currently the only secure aggregation mechanism; additive secret sharing and MPC-style masking are not implemented.
- **No empirical adversarial evaluation**: The privacy properties rely strictly on the mathematical bounds of the Gaussian mechanism; no gradient inversion, model inversion, or membership inference attacks have been empirically evaluated against the pipeline.
- **High default epsilon values**: At default parameters ($\Delta = 1.0, \sigma = 0.05, \delta = 10^{-5}$), the analytic single-round $\varepsilon$ is approximately $96.9$, representing a weak absolute privacy guarantee. The noise/utility trade-off has not yet been tuned for strong differential privacy.

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Set the required RDS database credentials and JWT secret:

```bash
export RDS_HOST="your-rds-host.amazonaws.com"
export RDS_PORT="5432"
export RDS_DBNAME="fedveil"
export RDS_USER="postgres"
export RDS_PASSWORD="your-db-password"
export JWT_SECRET="your-secure-random-jwt-secret"
```

*(On Windows PowerShell, use `$env:RDS_HOST = "..."`)*

### 3. Seed the Admin Account (One-Time Setup)
Create an admin account in the RDS database:
```bash
python scripts/seed_admin.py
```

### 4. Partition the Dataset (One-Time Setup)
Splits the Breast Cancer dataset into a server test set and 3 local client shards in `data/`:
```bash
python scripts/partition_data.py
```

### 5. Start the Coordinator Server
```bash
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

### 6. Authenticate & Register Clients

#### A. Log in to get an admin JWT
```bash
curl -X POST http://127.0.0.1:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

Response:
```json
{
  "token": "<jwt-token>"
}
```

#### B. Register clients using the Bearer token
```bash
curl -X POST http://127.0.0.1:8000/api/admin/register-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt-token>" \
  -d '{"client_id": "1", "name": "Client Node 1"}'
```

Response:
```json
{
  "status": "registered",
  "client_id": "1",
  "name": "Client Node 1",
  "api_key": "<generated-hex-api-key>"
}
```

Repeat for clients `2` and `3`.

### 7. Run the Clients
Run each client with its assigned `--id` and issued `--api-key`:

```bash
# Terminal 1: Client 1
python client.py --id 1 --api-key <CLIENT_1_API_KEY> --server http://127.0.0.1:8000

# Terminal 2: Client 2
python client.py --id 2 --api-key <CLIENT_2_API_KEY> --server http://127.0.0.1:8000

# Terminal 3: Client 3
python client.py --id 3 --api-key <CLIENT_3_API_KEY> --server http://127.0.0.1:8000
```

Clients can also be run continuously across rounds using `--loop`:
```bash
python client.py --id 1 --api-key <CLIENT_1_API_KEY> --server http://127.0.0.1:8000 --loop
```

### 8. (Optional) Run the Monitoring Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Running Tests

Run the test suite using `pytest`:

```bash
python -m pytest tests/ -v
```