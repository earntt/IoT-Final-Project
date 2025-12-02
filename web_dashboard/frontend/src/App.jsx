import React, { useState, useEffect } from 'react';
import { Activity, Thermometer, Droplets, Radio, AlertTriangle, Volume2, User, Power, Clock, History } from 'lucide-react';

export default function Dashboard() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  
  const [data, setData] = useState({
    timestamp: new Date().toISOString(),
    temperature: 22.5,
    humidity: 45,
    button: false,
    abnormal_movement: false,
    sound_alert: false,
    person_present: false,
    status: 'NORMAL'
  });

  const [history, setHistory] = useState([]);

  // Simulate real-time data updates
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/history", { cache: "no-store" });
        const json = await res.json();
        setHistory(json.slice(0, 50)); // แสดง 50 ล่าสุด
      } catch (err) {
        console.error("Failed to fetch history", err);
      }
    };

    fetchHistory();

    const ws = new WebSocket("ws://localhost:8000/ws");

    ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    console.log("REALTIME:", msg);

    if (!msg || !msg.timestamp || typeof msg.person_present === 'undefined') {
        console.warn("Skipping incomplete WebSocket message:", msg);
        return;
    }
    
    const completeMsg = {
        ...msg,
        button: Boolean(msg.button),
        abnormal_movement: Boolean(msg.abnormal_movement),
        sound_alert: Boolean(msg.sound_alert),
        person_present: Boolean(msg.person_present),
        status: msg.status.toUpperCase()
    };

    setData(completeMsg);

    setHistory(h => {
      console.log("HISTORY UPDATE:", completeMsg);
      if (h.length > 0 && h[0].timestamp === completeMsg.timestamp) return h;
      return [completeMsg, ...h].slice(0, 50); // limit 50
    });

  };

    return () => ws.close();
  }, []);

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  const formatFullDate = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const StatusBadge = ({ status }) => {
    const statusStyles = {
      NORMAL: 'bg-green-100 text-green-800',
      WARNING: 'bg-yellow-100 text-yellow-800',
      EMERGENCY: 'bg-red-100 text-red-800',
    };

    const style = statusStyles[status] || 'bg-gray-100 text-gray-800';

    return (
      <span className={`px-3 py-1 rounded-full text-sm font-semibold ${style}`}>
        {status}
      </span>
    );
  };


  const DataCard = ({ icon: Icon, title, value, alert, unit = '' }) => {
    let borderColor = 'border-blue-500';
    let bgColor = 'bg-blue-100';
    let iconColor = 'text-blue-600';

    if (alert === true || alert === 'EMERGENCY') {
      borderColor = 'border-red-500';
      bgColor = 'bg-red-100';
      iconColor = 'text-red-600';
    } else if (alert === 'WARNING') {
      borderColor = 'border-yellow-500';
      bgColor = 'bg-yellow-100';
      iconColor = 'text-yellow-600';
    }

    return (
      <div className={`bg-white rounded-lg shadow-md p-6 border-l-4 ${borderColor}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`p-3 rounded-full ${bgColor}`}>
              <Icon className={`w-6 h-6 ${iconColor}`} />
            </div>
            <div>
              <p className="text-sm text-gray-600 font-medium">{title}</p>
              <p className="text-2xl font-bold text-gray-800">
                {typeof value === 'boolean' ? (value ? 'YES' : 'NO') : value}
                {unit && <span className="text-lg ml-1">{unit}</span>}
              </p>
            </div>
          </div>

          {(alert === true || alert === 'EMERGENCY') && (
            <AlertTriangle className="w-8 h-8 text-red-500 animate-pulse" />
          )}
        </div>
      </div>
    );
  };


  const DashboardPage = () => (
    <>
      {/* Header */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
              <Activity className="w-8 h-8 text-blue-600" />
              Real-time Sensor Dashboard
            </h1>
            <p className="text-gray-600 mt-2">
              Last updated: {formatTime(data.timestamp)}
            </p>
          </div>
          <StatusBadge status={data.status} />
        </div>
      </div>

      {/* Data Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <DataCard
          icon={Thermometer}
          title="Temperature"
          value={data.temperature}
          unit="°C"
        />
        
        <DataCard
          icon={Droplets}
          title="Humidity"
          value={data.humidity}
          unit="%"
        />
        
        <DataCard
          icon={Radio}
          title="Button Status"
          value={data.button}
          alert={data.button}
        />
        
        <DataCard
          icon={AlertTriangle}
          title="Abnormal Movement"
          value={data.abnormal_movement}
          alert={data.abnormal_movement}
        />
        
        <DataCard
          icon={Volume2}
          title="Sound Alert"
          value={data.sound_alert}
          alert={data.sound_alert}
        />
        
        <DataCard
          icon={User}
          title="Person Present"
          value={data.person_present}
          alert={!data.person_present}
        />
        
        <DataCard
          icon={Power}
          title="Patient Status"
          value={data.status}
          alert={data.status}
        />
      </div>

      {/* Alert Summary */}
      {(data.abnormal_movement || data.sound_alert || data.button) && (
        <div className="mt-8 bg-red-50 border-l-4 border-red-500 rounded-lg shadow-md p-6">
          <div className="flex items-center gap-3 mb-3">
            <AlertTriangle className="w-6 h-6 text-red-600" />
            <h2 className="text-xl font-bold text-red-800">Active Alerts</h2>
          </div>
          <ul className="space-y-2">
            {data.abnormal_movement && (
              <li className="text-red-700 font-medium">⚠ Abnormal movement detected</li>
            )}
            {data.sound_alert && (
              <li className="text-red-700 font-medium">⚠ Sound alert triggered</li>
            )}
            {data.button && (
              <li className="text-red-700 font-medium">⚠ Button pressed</li>
            )}
          </ul>
        </div>
      )}
    </>
  );

  const HistoryPage = () => (
    <>
      {/* History Header */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Clock className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-3xl font-bold text-gray-800">Historical Log</h1>
              <p className="text-gray-600 mt-2">
                Total entries: {history.length}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Historical Log Table */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="overflow-x-auto">
          <div className="max-h-[600px] overflow-y-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Temp (°C)
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Humidity (%)
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Button
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Movement
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sound
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Person
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {history.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="px-4 py-8 text-center text-gray-500">
                      No historical data yet. Data will appear as it's collected...
                    </td>
                  </tr>
                ) : (
                  history.map((entry, index) => (
                    <tr
                      key={index}
                      className={`hover:bg-gray-50 ${
                        entry.status === 'EMERGENCY' ? 'bg-red-50'
                          : entry.status.toUpperCase() === 'WARNING'? 'bg-yellow-50'
                          : ''
                      }`}
                    >
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {formatFullDate(entry.timestamp)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {entry.temperature}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {entry.humidity}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm">
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                          entry.button ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {entry.button ? 'YES' : 'NO'}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm">
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                          entry.abnormal_movement ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {entry.abnormal_movement ? 'YES' : 'NO'}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm">
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                          entry.sound_alert ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {entry.sound_alert ? 'YES' : 'NO'}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm">
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                          entry.person_present ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {entry.person_present ? 'YES' : 'NO'}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm">
                        <span
                          className={`px-2 py-1 rounded-full text-xs font-semibold ${
                            {
                              NORMAL: 'bg-green-100 text-green-800',
                              WARNING: 'bg-yellow-100 text-yellow-800',
                              EMERGENCY: 'bg-red-100 text-red-800'
                            }[entry.status.toUpperCase()] || 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {entry.status.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Navigation Bar */}
      <nav className="bg-white shadow-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <Activity className="w-6 h-6 text-blue-600" />
              <span className="text-xl font-bold text-gray-800">Sensor System</span>
            </div>
            <div className="flex space-x-4">
              <button
                onClick={() => setCurrentPage('dashboard')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  currentPage === 'dashboard'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5" />
                  Dashboard
                </div>
              </button>
              <button
                onClick={() => setCurrentPage('history')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  currentPage === 'history'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <div className="flex items-center gap-2">
                  <History className="w-5 h-5" />
                  History
                </div>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Page Content */}
      <div className="max-w-7xl mx-auto p-8">
        {currentPage === 'dashboard' ? <DashboardPage /> : <HistoryPage />}
      </div>
    </div>
  );
}