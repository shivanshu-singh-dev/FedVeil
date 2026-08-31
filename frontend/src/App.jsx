import React, { useState, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [telemetry, setTelemetry] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  
  // Inference state
  const [sampleInput, setSampleInput] = useState('0.45, -0.12, 0.88, 0.31');
  const [prediction, setPrediction] = useState(null);

  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/telemetry`);
        if (res.ok) {
          const data = await res.json();
          setTelemetry(data);
          setIsRunning(data.status === 'running');
        }
      } catch (err) {
        console.error('API connection error:', err);
      }
    };

    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    setIsRunning(true);
    await fetch(`${API_BASE}/api/run-simulation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ num_clients: 5, num_rounds: 6, noise_scale: 0.05, vector_size: 4 })
    });
  };

  const handlePredict = async () => {
    const parsedFeatures = sampleInput.split(',').map(v => parseFloat(v.trim()) || 0.0);
    const res = await fetch(`${API_BASE}/api/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ features: parsedFeatures })
    });
    if (res.ok) {
      setPrediction(await res.json());
    }
  };

  const latestMetrics = telemetry?.rounds_data?.slice(-1)[0] || {};

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex justify-between items-center bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <div>
            <h1 className="text-2xl font-bold text-blue-600">FedVeil</h1>
            <p className="text-sm text-gray-500">Privacy-Preserving Federated Learning Demo</p>
          </div>
          <button 
            onClick={handleStart} 
            disabled={isRunning}
            className="bg-blue-600 text-white px-6 py-2 rounded font-semibold disabled:bg-gray-400"
          >
            {isRunning ? 'Running Simulation...' : 'Start Training'}
          </button>
        </div>

        {/* Core Metrics */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-lg border border-gray-200 text-center shadow-sm">
            <div className="text-sm text-gray-500 mb-1">Round</div>
            <div className="text-xl font-bold">{telemetry?.current_round || 0} / {telemetry?.total_rounds || 0}</div>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200 text-center shadow-sm">
            <div className="text-sm text-gray-500 mb-1">Privacy Budget (ε)</div>
            <div className="text-xl font-bold text-orange-500">{telemetry?.epsilon_note ? 'Per-Client' : (telemetry?.placeholder_epsilon ?? telemetry?.cumulative_epsilon ?? 0).toFixed(2)}</div>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200 text-center shadow-sm">
            <div className="text-sm text-gray-500 mb-1">Accuracy</div>
            <div className="text-xl font-bold text-green-600">{latestMetrics.accuracy ? `${latestMetrics.accuracy}%` : '--'}</div>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200 text-center shadow-sm">
            <div className="text-sm text-gray-500 mb-1">HE Overhead</div>
            <div className="text-xl font-bold text-purple-600">{latestMetrics.server_agg_ms ? `${latestMetrics.server_agg_ms} ms` : '--'}</div>
          </div>
        </div>

        {/* Client Status List */}
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <div className="flex justify-between items-center mb-4 border-b pb-2">
            <h2 className="text-lg font-bold">Client Node Status</h2>
            <span className="text-sm text-gray-500 font-medium">({telemetry?.clients_status?.length || 0} Active)</span>
          </div>
          <div className="space-y-3">
            {(telemetry?.clients_status || []).map(client => (
              <div key={client.id} className="flex justify-between items-center bg-gray-50 p-3 rounded border border-gray-100">
                <span className="font-medium text-gray-700">{client.name}</span>
                <span className="text-sm bg-blue-100 text-blue-800 px-3 py-1 rounded-full">{client.status}</span>
              </div>
            ))}
            {!telemetry?.clients_status?.length && <p className="text-sm text-gray-400">Waiting for registered clients to submit updates...</p>}
          </div>
        </div>

        {/* Simple Inference Sandbox */}
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <h2 className="text-lg font-bold mb-4 border-b pb-2">Test Decrypted Model</h2>
          <div className="flex space-x-4">
            <input 
              type="text" 
              value={sampleInput}
              onChange={(e) => setSampleInput(e.target.value)}
              className="flex-1 border border-gray-300 rounded px-4 py-2"
              placeholder="Enter feature numbers separated by commas"
            />
            <button 
              onClick={handlePredict}
              className="bg-gray-800 text-white px-6 py-2 rounded hover:bg-gray-700"
            >
              Predict
            </button>
          </div>
          
          {prediction && (
            <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded text-green-800">
              <strong>Result:</strong> {prediction.prediction} <br/>
              <span className="text-sm text-green-600">Confidence: {(prediction.confidence * 100).toFixed(1)}%</span>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}