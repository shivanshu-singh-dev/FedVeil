import React, { useState, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000';
const AGENT_BASE = 'http://127.0.0.1:8001';

export default function App() {
  const [activeTab, setActiveTab] = useState('client');
  const [token, setToken] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [telemetry, setTelemetry] = useState(null);
  const [adminClients, setAdminClients] = useState([]);

  // Client Console State
  const [clients, setClients] = useState([
    { id: '1', apiKey: '', log: 'Ready for training.', status: 'Idle', weights: [] },
    { id: '2', apiKey: '', log: 'Ready for training.', status: 'Idle', weights: [] },
    { id: '3', apiKey: '', log: 'Ready for training.', status: 'Idle', weights: [] }
  ]);

  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/telemetry`);
        if (res.ok) setTelemetry(await res.json());
      } catch (err) {
        console.error('API connection error:', err);
      }
    };
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchClients = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/admin/clients`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAdminClients(data.clients || []);
      }
    } catch (err) {
      console.error('Failed to fetch clients list', err);
    }
  };

  useEffect(() => {
    fetchClients();
  }, [token]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    try {
      const res = await fetch(`${API_BASE}/api/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      if (res.ok) {
        const data = await res.json();
        setToken(data.token);
      } else {
        setLoginError('Invalid credentials');
      }
    } catch (err) {
      setLoginError('Server connection failed');
    }
  };

  const updateClientState = (id, field, value) => {
    setClients(prev => prev.map(c => c.id === id ? { ...c, [field]: value } : c));
  };

  const runAllClients = async () => {
    const validClients = clients.filter(c => c.apiKey).map(c => ({ client_id: c.id, api_key: c.apiKey }));
    if (validClients.length === 0) return alert('Enter at least one API key first.');
    
    clients.forEach(c => { 
      if(c.apiKey) {
        updateClientState(c.id, 'log', 'Executing orchestrated Run-All sequence...');
        updateClientState(c.id, 'status', 'Training');
      }
    });
    
    try {
      const res = await fetch(`${AGENT_BASE}/run-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clients: validClients })
      });
      const data = await res.json();
      if (res.ok) {
         data.results.forEach(r => {
           const logMsg = r.status === 'success' ? `Aggregated! Response: ${JSON.stringify(r.server_response)}` : `Error: ${r.detail}`;
           updateClientState(r.client_id, 'log', logMsg);
           updateClientState(r.client_id, 'status', r.status === 'success' ? 'Synced' : 'Error');
           
           const weights = r.server_response?.current_weights;
           if (weights) {
             updateClientState(r.client_id, 'weights', weights);
           }
         });
      }
    } catch(err) {
        alert("Network Error: Could not reach client_agent.py");
        clients.forEach(c => updateClientState(c.id, 'status', 'Offline'));
    }
  };

  const rounds = telemetry?.rounds_data || [];
  const latestMetrics = rounds.length > 0 ? rounds[rounds.length - 1] : {};

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 p-8 font-sans">
      <div className="max-w-5xl mx-auto space-y-6">
        
        {/* Header & Tabs */}
        <div className="flex justify-between items-center bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <div>
            <h1 className="text-2xl font-bold text-blue-600">FedVeil</h1>
            <p className="text-sm text-gray-500">Privacy-Preserving Federated Learning Demo</p>
          </div>
          <div className="flex space-x-2">
            <button 
              onClick={() => setActiveTab('client')}
              className={`px-4 py-2 rounded font-semibold transition-colors ${activeTab === 'client' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
            >
              Client Console
            </button>
            <button 
              onClick={() => setActiveTab('admin')}
              className={`px-4 py-2 rounded font-semibold transition-colors ${activeTab === 'admin' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
            >
              Admin Dashboard
            </button>
          </div>
        </div>

        {/* Client Console Tab */}
        {activeTab === 'client' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
              <h2 className="text-xl font-bold text-gray-800">Simulated Participants</h2>
              <button 
                onClick={runAllClients}
                className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-2 rounded font-semibold shadow transition"
              >
                Run All Active Clients
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {clients.map(client => (
                <div key={client.id} className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm flex flex-col space-y-4">
                  <div className="flex justify-between items-center border-b pb-2">
                    <h3 className="font-bold text-lg text-gray-800">Client Node {client.id}</h3>
                    <span className={`text-xs px-2 py-1 rounded font-semibold ${
                      client.status === 'Synced' ? 'bg-green-100 text-green-700' :
                      client.status === 'Training' ? 'bg-blue-100 text-blue-700 animate-pulse' :
                      client.status === 'Error' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {client.status}
                    </span>
                  </div>
                  
                  <div>
                    <label className="block text-xs font-bold text-gray-500 uppercase tracking-wide mb-1">Authorization</label>
                    <input 
                      type="password" 
                      value={client.apiKey}
                      onChange={(e) => updateClientState(client.id, 'apiKey', e.target.value)}
                      placeholder="Paste 16-byte API key..."
                      className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    />
                  </div>

                  {/* Restored Raw JSON Terminal Log Box */}
                  <div className="bg-slate-900 text-green-400 p-3 rounded font-mono text-xs h-32 overflow-y-auto break-words shadow-inner">
                    &gt; {client.log}
                  </div>

                  {/* Collapsible Model Weights Preview */}
                  {client.weights.length > 0 && (
                    <details className="text-xs bg-gray-50 border border-gray-200 rounded p-2">
                      <summary className="font-semibold cursor-pointer text-gray-700 hover:text-blue-600">
                        📦 Synced Global Weights ({client.weights.length} params)
                      </summary>
                      <div className="mt-2 font-mono text-[10px] text-gray-600 max-h-24 overflow-y-auto bg-white p-2 border rounded">
                        {JSON.stringify(client.weights)}
                      </div>
                    </details>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Admin Login Gate */}
        {activeTab === 'admin' && !token && (
          <form onSubmit={handleLogin} className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm max-w-sm mx-auto space-y-4">
            <h2 className="text-xl font-bold mb-4">Admin Login</h2>
            {loginError && <p className="text-red-500 text-sm">{loginError}</p>}
            <input 
              type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)}
              className="w-full border border-gray-300 rounded px-4 py-2" required
            />
            <input 
              type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded px-4 py-2" required
            />
            <button type="submit" className="w-full bg-blue-600 text-white px-4 py-2 rounded font-semibold">Authenticate</button>
          </form>
        )}

        {/* Protected Admin Dashboard */}
        {activeTab === 'admin' && token && (
          <div className="space-y-6">
            <div className="bg-green-50 p-4 rounded text-green-800 border border-green-200 flex justify-between items-center">
              <span>Logged in securely via JWT.</span>
              <div className="space-x-4">
                <button 
                  onClick={async () => {
                    if (confirm("Are you sure you want to wipe all clients, rounds, and logs?")) {
                      const res = await fetch(`${API_BASE}/api/admin/reset`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${token}` }
                      });
                      if (res.ok) {
                        alert("Database reset successfully!");
                        window.location.reload();
                      }
                    }
                  }}
                  className="bg-red-600 text-white px-3 py-1 rounded text-sm font-semibold hover:bg-red-700 transition"
                >
                  Reset Database
                </button>
                <button onClick={() => setToken(null)} className="text-sm font-bold underline hover:text-green-900">Logout</button>
              </div>
            </div>
            
            {/* 3 Clean Metric Cards */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white p-4 rounded-lg border border-gray-200 text-center shadow-sm">
                <div className="text-sm text-gray-500 mb-1">Current Round</div>
                <div className="text-xl font-bold">{telemetry?.current_round ?? 0}</div>
              </div>
              <div className="bg-white p-4 rounded-lg border border-gray-200 text-center shadow-sm">
                <div className="text-sm text-gray-500 mb-1">Privacy Budget (ε) Logged</div>
                <div className="text-xl font-bold text-orange-500">Active Tracking</div>
              </div>
              <div className="bg-white p-4 rounded-lg border border-gray-200 text-center shadow-sm">
                <div className="text-sm text-gray-500 mb-1">Global Accuracy</div>
                <div className="text-xl font-bold text-green-600">{latestMetrics.accuracy ? `${latestMetrics.accuracy}%` : '--'}</div>
              </div>
            </div>

            {/* Client Management Panel */}
            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm space-y-6">
              <div className="flex justify-between items-center border-b pb-2">
                <h2 className="text-lg font-bold">Client Node Registry & Telemetry</h2>
                <button 
                  onClick={fetchClients}
                  className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-1 rounded text-xs font-semibold transition flex items-center space-x-1"
                >
                  <span>🔄 Refresh List</span>
                </button>
              </div>

              {/* Simplified Registered Clients Table */}
              <div>
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-left border-collapse text-sm">
                    <thead>
                      <tr className="bg-gray-100 border-b text-gray-600">
                        <th className="p-3 font-semibold">Client ID</th>
                        <th className="p-3 font-semibold">Node Name</th>
                      </tr>
                    </thead>
                    <tbody>
                      {adminClients.map(c => (
                        <tr key={c.client_id} className="border-b hover:bg-gray-50">
                          <td className="p-3 font-mono font-bold text-blue-600">{c.client_id}</td>
                          <td className="p-3 text-gray-800">{c.name}</td>
                        </tr>
                      ))}
                      {adminClients.length === 0 && (
                        <tr>
                          <td colSpan="2" className="p-4 text-center text-gray-400 italic">No client nodes registered yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}