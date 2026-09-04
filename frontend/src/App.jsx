import React, { useState, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000';
const AGENT_BASE = 'http://127.0.0.1:8001';

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

export default function App() {
  const [activeTab, setActiveTab] = useState('client');
  const [token, setToken] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [telemetry, setTelemetry] = useState(null);
  const [adminClients, setAdminClients] = useState([]);
  
  // State for Dark Mode
  const [isDark, setIsDark] = useState(false);

  const [clients, setClients] = useState([
    { id: '1', apiKey: '', log: '> Ready for training.', status: 'Idle', weights: [] },
    { id: '2', apiKey: '', log: '> Ready for training.', status: 'Idle', weights: [] },
    { id: '3', apiKey: '', log: '> Ready for training.', status: 'Idle', weights: [] }
  ]);

  // Standard Clean Dark/Light Theme Dictionary
  const theme = {
    bg: isDark ? 'bg-gray-900 text-gray-100' : 'bg-gray-50 text-gray-900',
    panel: isDark ? 'bg-gray-800 border-gray-700 shadow-md' : 'bg-white border-gray-200 shadow-sm',
    textMain: isDark ? 'text-gray-100' : 'text-gray-800',
    textMuted: isDark ? 'text-gray-400' : 'text-gray-500',
    textAccent: isDark ? 'text-blue-400' : 'text-blue-600',
    border: isDark ? 'border-gray-700' : 'border-gray-200',
    input: isDark ? 'bg-gray-900 border-gray-600 text-gray-100 placeholder-gray-500 focus:ring-blue-500' : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400 focus:ring-blue-500',
    btnPrimary: isDark ? 'bg-purple-600 hover:bg-purple-500 text-white' : 'bg-purple-600 hover:bg-purple-700 text-white',
    tabActive: isDark ? 'bg-blue-600 text-white' : 'bg-blue-600 text-white',
    tabInactive: isDark ? 'bg-gray-700 text-gray-300 hover:bg-gray-600' : 'bg-gray-200 text-gray-700 hover:bg-gray-300',
    tableHead: isDark ? 'bg-gray-900 border-gray-700 text-gray-300' : 'bg-gray-100 border-b text-gray-600',
    tableRow: isDark ? 'border-gray-700 hover:bg-gray-700/50' : 'border-b hover:bg-gray-50',
    terminal: 'bg-slate-900 text-green-400 border border-transparent'
  };

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
      // Handle expired or invalid JWT token automatically
      if (res.status === 401) {
        setToken(null);
        return;
      }
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
        updateClientState(c.id, 'status', 'Training');
        updateClientState(c.id, 'log', '> Initializing local dataset...');
      }
    });
    await delay(600);

    clients.forEach(c => { 
      if(c.apiKey) updateClientState(c.id, 'log', '> Initializing local dataset...\n> Training local model...');
    });
    await delay(600);

    clients.forEach(c => { 
      if(c.apiKey) updateClientState(c.id, 'log', '> Initializing local dataset...\n> Training local model...\n> Applying DP noise (ε)...');
    });
    await delay(600);

    clients.forEach(c => { 
      if(c.apiKey) updateClientState(c.id, 'log', '> Initializing local dataset...\n> Training local model...\n> Applying DP noise (ε)...\n> Encrypting weights (Paillier HE)...\n> Submitting to coordinator...');
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
           const finalMsg = r.status === 'success' ? `> Aggregated! Response: ${JSON.stringify(r.server_response)}` : `> Error: ${r.detail}`;
           const fullLog = `> Initializing local dataset...\n> Training local model...\n> Applying DP noise (ε)...\n> Encrypting weights (Paillier HE)...\n> Submitting to coordinator...\n${finalMsg}`;
           
           updateClientState(r.client_id, 'log', fullLog);
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
    <div className={`min-h-screen p-8 font-sans transition-colors duration-300 ${theme.bg}`}>
      <div className="max-w-5xl mx-auto space-y-6">
        
        {/* Header & Tabs */}
        <div className={`flex justify-between items-center p-6 rounded-lg border ${theme.panel}`}>
          <div>
            <h1 className={`text-2xl font-bold ${theme.textAccent}`}>FedVeil</h1>
            <p className={`text-sm ${theme.textMuted}`}>Privacy-Preserving Federated Learning Demo</p>
          </div>
          <div className="flex space-x-4 items-center">
            {/* Dark Mode Toggle */}
            <button 
              onClick={() => setIsDark(!isDark)} 
              className={`px-3 py-1 text-sm font-semibold rounded-full border transition ${isDark ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : 'border-gray-300 text-gray-600 hover:bg-gray-100'}`}
              title="Toggle Theme"
            >
              {isDark ? 'Light' : 'Dark'}
            </button>
            <div className="flex space-x-2">
              <button 
                onClick={() => setActiveTab('client')}
                className={`px-4 py-2 rounded font-semibold transition-colors ${activeTab === 'client' ? theme.tabActive : theme.tabInactive}`}
              >
                Client Console
              </button>
              <button 
                onClick={() => setActiveTab('admin')}
                className={`px-4 py-2 rounded font-semibold transition-colors ${activeTab === 'admin' ? theme.tabActive : theme.tabInactive}`}
              >
                Admin Dashboard
              </button>
            </div>
          </div>
        </div>

        {/* Client Console Tab */}
        {activeTab === 'client' && (
          <div className="space-y-6">
            <div className={`flex justify-between items-center p-4 rounded-lg border ${theme.panel}`}>
              <h2 className={`text-xl font-bold ${theme.textMain}`}>Simulated Participants</h2>
              <button 
                onClick={runAllClients}
                className={`${theme.btnPrimary} px-6 py-2 rounded font-semibold shadow transition`}
              >
                Run All Active Clients
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {clients.map(client => (
                <div key={client.id} className={`p-5 rounded-lg border flex flex-col space-y-4 ${theme.panel}`}>
                  <div className={`flex justify-between items-center border-b pb-2 ${theme.border}`}>
                    <h3 className={`font-bold text-lg ${theme.textMain}`}>Client Node {client.id}</h3>
                    <span className={`text-xs px-2 py-1 rounded font-semibold ${
                      client.status === 'Synced' ? (isDark ? 'bg-green-900/40 text-green-400' : 'bg-green-100 text-green-700') :
                      client.status === 'Training' ? (isDark ? 'bg-blue-900/40 text-blue-400 animate-pulse' : 'bg-blue-100 text-blue-700 animate-pulse') :
                      client.status === 'Error' ? (isDark ? 'bg-red-900/40 text-red-400' : 'bg-red-100 text-red-700') : 
                      (isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600')
                    }`}>
                      {client.status}
                    </span>
                  </div>
                  
                  <div>
                    <label className={`block text-xs font-bold uppercase tracking-wide mb-1 ${theme.textMuted}`}>Authorization</label>
                    <input 
                      type="password" 
                      value={client.apiKey}
                      onChange={(e) => updateClientState(client.id, 'apiKey', e.target.value)}
                      placeholder="Paste 16-byte API key..."
                      className={`w-full rounded px-3 py-2 text-sm font-mono border focus:outline-none ${theme.input}`}
                    />
                  </div>

                  <div className={`p-3 rounded font-mono text-xs h-32 overflow-y-auto break-words shadow-inner whitespace-pre-wrap ${theme.terminal}`}>
                    {client.log}
                  </div>

                  {client.weights.length > 0 && (
                    <details className={`text-xs border rounded p-2 ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-gray-50 border-gray-200'}`}>
                      <summary className={`font-semibold cursor-pointer ${theme.textMain} hover:${theme.textAccent}`}>
                        Synced Global Weights ({client.weights.length} params)
                      </summary>
                      <div className={`mt-2 font-mono text-[10px] max-h-24 overflow-y-auto p-2 border rounded ${isDark ? 'bg-gray-950 text-gray-400 border-gray-700' : 'bg-white text-gray-600 border-gray-200'}`}>
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
          <form onSubmit={handleLogin} className={`p-6 rounded-lg border max-w-sm mx-auto space-y-4 ${theme.panel}`}>
            <h2 className={`text-xl font-bold mb-4 ${theme.textMain}`}>Admin Login</h2>
            {loginError && <p className="text-red-500 text-sm">{loginError}</p>}
            <input 
              type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)}
              className={`w-full rounded px-4 py-2 border ${theme.input}`} required
            />
            <input 
              type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
              className={`w-full rounded px-4 py-2 border ${theme.input}`} required
            />
            <button type="submit" className={`w-full px-4 py-2 rounded font-semibold ${isDark ? 'bg-blue-600 text-white hover:bg-blue-500' : 'bg-blue-600 text-white hover:bg-blue-700'}`}>Authenticate</button>
          </form>
        )}

        {/* Protected Admin Dashboard */}
        {activeTab === 'admin' && token && (
          <div className="space-y-6">
            <div className={`p-4 rounded border flex justify-between items-center ${isDark ? 'bg-green-900/20 border-green-800 text-green-400' : 'bg-green-50 border-green-200 text-green-800'}`}>
              <span>Logged in securely via JWT.</span>
              <div className="space-x-4 flex items-center">
                <button 
                  onClick={async () => {
                    if (confirm("Are you sure you want to reset training rounds to 0? (Clients will remain registered)")) {
                      const res = await fetch(`${API_BASE}/api/admin/reset-rounds`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${token}` }
                      });
                      if (res.status === 401) { setToken(null); return; }
                      if (res.ok) {
                        alert("Rounds reset to 0 successfully!");
                        setClients(prev => prev.map(c => ({...c, log: '> Ready for training.', status: 'Idle', weights: []})));
                      }
                    }
                  }}
                  className={`px-3 py-1 rounded text-sm font-semibold transition ${isDark ? 'bg-yellow-600 text-white hover:bg-yellow-500' : 'bg-yellow-500 text-white hover:bg-yellow-600'}`}
                >
                  Reset Rounds
                </button>

                <button 
                  onClick={async () => {
                    if (confirm("Are you sure you want to wipe all clients, rounds, and logs?")) {
                      const res = await fetch(`${API_BASE}/api/admin/reset`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${token}` }
                      });
                      if (res.status === 401) { setToken(null); return; }
                      if (res.ok) {
                        alert("Database wiped successfully!");
                        setAdminClients([]);
                        setClients(prev => prev.map(c => ({...c, apiKey: '', log: '> Ready for training.', status: 'Idle', weights: []})));
                      }
                    }
                  }}
                  className={`px-3 py-1 rounded text-sm font-semibold transition ${isDark ? 'bg-red-600 text-white hover:bg-red-500' : 'bg-red-600 text-white hover:bg-red-700'}`}
                >
                  Hard Reset
                </button>
                <button onClick={() => setToken(null)} className={`text-sm font-bold underline ${isDark ? 'hover:text-gray-300 text-gray-400' : 'hover:text-gray-900 text-gray-700'}`}>Logout</button>
              </div>
            </div>
            
            <div className="grid grid-cols-3 gap-4">
              <div className={`p-4 rounded-lg border text-center ${theme.panel}`}>
                <div className={`text-sm mb-1 ${theme.textMuted}`}>Current Round</div>
                <div className={`text-xl font-bold ${theme.textMain}`}>{telemetry?.current_round ?? 0}</div>
              </div>
              <div className={`p-4 rounded-lg border text-center ${theme.panel}`}>
                <div className={`text-sm mb-1 ${theme.textMuted}`}>Privacy Budget (ε) Logged</div>
                <div className="text-xl font-bold text-orange-500">Active Tracking</div>
              </div>
              <div className={`p-4 rounded-lg border text-center ${theme.panel}`}>
                <div className={`text-sm mb-1 ${theme.textMuted}`}>Global Accuracy</div>
                <div className={`text-xl font-bold ${isDark ? 'text-green-400' : 'text-green-600'}`}>{latestMetrics.accuracy ? `${latestMetrics.accuracy}%` : '--'}</div>
              </div>
            </div>

            <div className={`p-6 rounded-lg border space-y-6 ${theme.panel}`}>
              <div className={`flex justify-between items-center border-b pb-2 ${theme.border}`}>
                <h2 className={`text-lg font-bold ${theme.textMain}`}>Client Node Registry & Telemetry</h2>
                <button 
                  onClick={fetchClients}
                  className={`px-3 py-1 rounded text-xs font-semibold transition flex items-center space-x-1 ${isDark ? 'bg-gray-700 text-gray-200 hover:bg-gray-600' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
                >
                  <span>🔄 Refresh List</span>
                </button>
              </div>

              <div>
                <div className={`border rounded-lg overflow-hidden ${theme.border}`}>
                  <table className="w-full text-left border-collapse text-sm">
                    <thead>
                      <tr className={theme.tableHead}>
                        <th className="p-3 font-semibold">Client ID</th>
                        <th className="p-3 font-semibold">Node Name</th>
                        <th className="p-3 font-semibold">Cumulative ε</th>
                      </tr>
                    </thead>
                    <tbody>
                      {adminClients.map(c => (
                        <tr key={c.client_id} className={`transition-colors ${theme.tableRow}`}>
                          <td className={`p-3 font-mono font-bold ${theme.textAccent}`}>{c.client_id}</td>
                          <td className={`p-3 ${theme.textMain}`}>{c.name}</td>
                          <td className="p-3 text-orange-500 font-mono font-semibold">
                            {c.cumulative_epsilon !== undefined && c.cumulative_epsilon !== null ? Number(c.cumulative_epsilon).toFixed(4) : '0.0000'}
                          </td>
                        </tr>
                      ))}
                      {adminClients.length === 0 && (
                        <tr>
                          <td colSpan="3" className={`p-4 text-center italic ${theme.textMuted}`}>No client nodes registered yet.</td>
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