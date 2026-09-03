from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uvicorn

# Import the existing logic from the CLI script
from client import run_client_round

app = FastAPI(title="FedVeil Client Agent")

# Allow the React frontend to communicate with this agent
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ClientConfig(BaseModel):
    client_id: str
    api_key: str

class RoundRequest(BaseModel):
    client_id: str
    api_key: str
    server_url: str = "http://127.0.0.1:8000"

class RunAllRequest(BaseModel):
    clients: List[ClientConfig]
    server_url: str = "http://127.0.0.1:8000"

@app.post("/run-round")
def run_round(req: RoundRequest):
    """Runs a single federated learning round for one specific client."""
    try:
        resp = run_client_round(
            client_id=req.client_id,
            api_key=req.api_key,
            server_url=req.server_url
        )
        return {
            "status": "success", 
            "client_id": req.client_id, 
            "log": f"Client {req.client_id} training & encryption completed.",
            "server_response": resp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-all")
def run_all(req: RunAllRequest):
    """
    Orchestrates all active clients to submit updates for the current round.
    Ensures that once aggregation completes on the final client, 
    the final synchronized global state is shared across all results.
    """
    results = []
    final_aggregated_response = None

    # Step 1: Execute all client training routines and submit payloads
    for client in req.clients:
        try:
            resp = run_client_round(
                client_id=client.client_id,
                api_key=client.api_key,
                server_url=req.server_url
            )
            
            # If this response triggered the final aggregation, capture it
            if isinstance(resp, dict) and resp.get("status") == "aggregated":
                final_aggregated_response = resp

            results.append({
                "client_id": client.client_id, 
                "status": "success", 
                "server_response": resp
            })
        except Exception as e:
            results.append({
                "client_id": client.client_id, 
                "status": "error", 
                "detail": str(e)
            })
    
    # Step 2: If aggregation occurred, enrich all successful results with the final unified weights
    if final_aggregated_response:
        for r in results:
            if r["status"] == "success" and isinstance(r.get("server_response"), dict):
                # Ensure every client receives the final aggregated global weights
                r["server_response"]["current_weights"] = final_aggregated_response.get("current_weights")

    return {"status": "completed", "results": results}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)