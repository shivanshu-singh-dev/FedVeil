# FedVeil

FedVeil is an academic prototype for federated learning across simulated clients, using **Paillier homomorphic encryption** for secure aggregation and **Gaussian-noise differential privacy**. It includes AWS RDS Postgres-backed persistence for round history, global weights, client registry, and privacy accounting, with JWT-based admin authentication and API-key-based client authentication.

---

## What This Does

* **Real local model training:** Implements full-batch gradient descent for logistic regression on real partitioned data (the Breast Cancer Wisconsin diagnostic dataset), rather than random placeholder vectors.
* **Real Paillier homomorphic encryption:** Clients encrypt parameter updates locally with the coordinator's public key; the coordinator sums the encrypted ciphertexts homomorphically without decrypting individual client updates.
* **Real differential privacy:** Applies Gaussian perturbation to local weight updates prior to encryption, with privacy budget ($\varepsilon$) computed using the analytic Gaussian mechanism formula rather than fixed placeholder values.
* **Persistent RDS Postgres storage:** Persists state across four database tables in AWS RDS Postgres:

  * `rounds`: Stores round history, global model weights (as JSONB), test accuracy, loss, and aggregation latency.
  * `privacy_log`: Logs per-client, per-round $\varepsilon$ expenditures with UTC timestamps.
  * `clients`: Tracks registered clients and their generated API keys.
  * `admins`: Stores admin usernames and bcrypt password hashes.
* **Model state restore:** Restores the latest global weights and current round number from the database on coordinator startup.
* **JWT-based admin authentication:** Protects administrative endpoints using bcrypt password verification, a login endpoint issuing signed JSON Web Tokens (JWTs), and Bearer token authorization.
* **Client authentication:** Requires clients to be pre-registered via the admin API and provide a valid 16-byte hex API key with each submission before updates are accepted.
* **Modular Client Agent & Monitoring Dashboard:** Features a dedicated client agent service (`client_agent.py`) wrapping local execution and a modern React frontend featuring two primary tabs: an **Admin Dashboard** and a **Client Console** for managing participant nodes, terminal execution logs, and cumulative epsilon tracking.

---

## Known Limitations

* **Centralized key custody:** The coordinator generates and holds both the Paillier public and private keys, decrypting the aggregate directly. Because threshold or multi-party decryption is not implemented, a compromised coordinator could decrypt individual client ciphertexts before aggregation.
* **No MPC masking:** Homomorphic encryption is currently the only secure aggregation mechanism; additive secret sharing and MPC-style masking are not implemented.
* **No empirical adversarial evaluation:** The privacy properties rely strictly on the mathematical bounds of the Gaussian mechanism; no gradient inversion, model inversion, or membership inference attacks have been empirically evaluated against the pipeline.
* **High default epsilon values:** At default parameters ($\Delta = 1.0$, $\sigma = 0.05$, $\delta = 10^{-5}$), the analytic single-round $\varepsilon$ is approximately **96.9**, representing a weak absolute privacy guarantee. The noise/utility trade-off has not yet been tuned for strong differential privacy.

---

## Quick Start

### 1. Create and Activate the Python Virtual Environment

It is recommended to use a Python virtual environment to isolate FedVeil's dependencies.

#### Windows PowerShell

From the project root directory:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

After activation, your terminal should show `(venv)`:

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Python Dependencies

Once the virtual environment is activated, install the required Python packages:

```bash
pip install -r requirements.txt
```

You should see `(venv)` at the beginning of your terminal prompt while the environment is active.

### 3. Configure Environment Variables

Set the required RDS database credentials and JWT secret.

#### Windows PowerShell

```powershell
$env:RDS_HOST = "your-rds-host.amazonaws.com"
$env:RDS_PORT = "5432"
$env:RDS_DBNAME = "fedveil"
$env:RDS_USER = "postgres"
$env:RDS_PASSWORD = "your-db-password"
$env:JWT_SECRET = "your-secure-random-jwt-secret"
```

#### macOS / Linux

```bash
export RDS_HOST="your-rds-host.amazonaws.com"
export RDS_PORT="5432"
export RDS_DBNAME="fedveil"
export RDS_USER="postgres"
export RDS_PASSWORD="your-db-password"
export JWT_SECRET="your-secure-random-jwt-secret"
```

### 4. Seed the Admin Account (One-Time Setup)

Create an admin account in the RDS database:

```bash
python -m scripts.seed_admin
```

### 5. Partition the Dataset (One-Time Setup)

Split the Breast Cancer dataset into a server test set and three local client shards in `data/`:

```bash
python scripts/partition_data.py
```

### 6. Start the Services

To run the system, open separate terminal windows for each component.

> **Important:** If you open a new terminal, activate the virtual environment again before running the Python services.

#### A. Start the Coordinator Server

The coordinator runs on port `8000`:

```powershell
.\venv\Scripts\activate
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

#### B. Start the Client Agent Service

The client agent runs on port `8001`:

```powershell
.\venv\Scripts\activate
python client_agent.py
```

#### C. Start the Monitoring Frontend

Open a terminal in the `frontend` directory:

```powershell
cd frontend
npm install
npm run dev
```

---

## Deactivating the Virtual Environment

When you are finished working with FedVeil, you can deactivate the virtual environment with:

```powershell
deactivate
```

To work on FedVeil again, simply activate it:

```powershell
.\venv\Scripts\activate
```


## Usage Guide

The system can be operated through the **React frontend** or directly through the **API**.

### 1. Authenticate & Register Clients

You can register clients using the Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Or use the API directly with `curl`.

#### Log in to Get an Admin JWT

```bash
curl -X POST http://127.0.0.1:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

The response will contain a JWT token. Use this token when making authenticated admin requests.

#### Register Clients Using the Bearer Token

```bash
curl -X POST http://127.0.0.1:8000/api/admin/register-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt-token>" \
  -d '{"client_id": "1", "name": "Client Node 1"}'
```

Repeat the registration process for clients `2` and `3`.

---

### 2. Run Client Nodes via the Frontend Client Console

1. Navigate to the React frontend URL provided by Vite, typically:

   ```text
   http://localhost:5173
   ```

2. Open the **Client Console** tab.

3. Paste the generated 16-byte hexadecimal API keys into the respective fields for:

   * Client Node 1
   * Client Node 2
   * Client Node 3

4. Click **Run All Active Clients**.

The client agent will orchestrate:

* Local model training
* Gaussian differential privacy noise addition
* Paillier homomorphic encryption
* Secure aggregation
* Global model update

---

## Running Tests

Run the test suite using `pytest`:

```bash
python -m pytest tests/ -v
```

---

## Project Architecture

At a high level, FedVeil consists of the following components:

```text
                         ┌─────────────────────┐
                         │   React Frontend    │
                         │  Admin Dashboard    │
                         │  Client Console     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Client Agent     │
                         │     Port 8001       │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
             ┌─────────────┐                ┌─────────────┐
             │  Client 1   │                │  Client 2   │
             │ Local Data  │                │ Local Data  │
             └──────┬──────┘                └──────┬──────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Coordinator Server  │
                         │     Port 8000       │
                         │                     │
                         │ • Model aggregation │
                         │ • Paillier HE       │
                         │ • Differential      │
                         │   Privacy           │
                         │ • JWT authentication│
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     AWS RDS         │
                         │     PostgreSQL      │
                         │                     │
                         │ • rounds            │
                         │ • privacy_log       │
                         │ • clients           │
                         │ • admins            │
                         └─────────────────────┘
```

---

## Security & Privacy Notes

FedVeil combines several security mechanisms:

| Mechanism                           | Purpose                                                             |
| ----------------------------------- | ------------------------------------------------------------------- |
| **Paillier Homomorphic Encryption** | Protects client model updates during transmission and aggregation   |
| **Gaussian Differential Privacy**   | Adds statistical noise to local updates                             |
| **JWT Authentication**              | Protects administrative API endpoints                               |
| **API Keys**                        | Authenticates registered client nodes                               |
| **bcrypt**                          | Securely hashes administrator passwords                             |
| **AWS RDS PostgreSQL**              | Provides persistent storage for system state and privacy accounting |

The current implementation should be considered an **academic prototype**, not a production-ready privacy-preserving federated learning system.

---

## License

This project is intended for academic and research purposes.
