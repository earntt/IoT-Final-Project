import React, { useState, useEffect } from 'react';
import { Activity, Thermometer, Droplets, Radio, AlertTriangle, Volume2, User, Power, Clock, History } from 'lucide-react';

// Component definitions outside of render
const StatusBadge = ({ status }) => {
  const statusStyles = {
    NORMAL: 'bg-green-100 text-green-800',
    WARNING: 'bg-yellow-100 text-yellow-800',
    EMERGENCY: 'bg-red-100 text-red-800',
  };

  const style = statusStyles[status] || 'bg-gray-100 text-gray-800';

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${style}`}>
      {status.toUpperCase()}
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

const DashboardPage = ({ data, formatTime, deviceStatus, onControlChange, lightOn, handleLightSwitch, wsConnected }) => (
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
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className="text-gray-600">{wsConnected ? 'Live' : 'Disconnected'}</span>
          </div>
          <StatusBadge status={data.status} />
        </div>
      </div>
    </div>

    {/* Device Status & Control */}
    <div className="bg-white rounded-lg shadow-md p-6 mb-8">
      <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
        <Power className="w-6 h-6 text-blue-600" />
        Device Status & Control
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ESP32 Status & Control */}
        <div className="border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${deviceStatus.esp32_online ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
              <span className="font-semibold text-gray-800">ESP32 Sensor Node</span>
            </div>
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${deviceStatus.esp32_online ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
              {deviceStatus.esp32_online ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Sensor Reading</span>
            <button
              onClick={() => onControlChange('esp32', !deviceStatus.esp32_control)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                deviceStatus.esp32_control
                  ? 'bg-green-500 text-white hover:bg-green-600'
                  : 'bg-gray-300 text-gray-700 hover:bg-gray-400'
              }`}
            >
              {deviceStatus.esp32_control ? 'ENABLED' : 'DISABLED'}
            </button>
          </div>
        </div>

        {/* Pi Gateway Status & Control */}
        <div className="border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${deviceStatus.pi_online ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
              <span className="font-semibold text-gray-800">Raspberry Pi Gateway</span>
            </div>
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${deviceStatus.pi_online ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
              {deviceStatus.pi_online ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Data Processing</span>
            <button
              onClick={() => onControlChange('pi', !deviceStatus.pi_control)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                deviceStatus.pi_control
                  ? 'bg-green-500 text-white hover:bg-green-600'
                  : 'bg-gray-300 text-gray-700 hover:bg-gray-400'
              }`}
            >
              {deviceStatus.pi_control ? 'ENABLED' : 'DISABLED'}
            </button>
          </div>
        </div>
      </div>
    </div>

    {/* Light Switch Control */}
    <div className="bg-white rounded-lg shadow-md p-6 mb-8">
      <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
        <Power className="w-6 h-6 text-blue-600" />
        Light Switch Control
      </h2>
      <div className="flex items-center justify-center gap-6">
        <button
          onClick={() => handleLightSwitch(false)}
          className={`px-8 py-4 rounded-lg font-bold text-lg transition-all ${
            !lightOn
              ? 'bg-gray-600 text-white shadow-lg scale-105'
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
        >
          OFF
        </button>
        <div className="flex flex-col items-center">
          <div className={`w-20 h-20 rounded-full flex items-center justify-center transition-all ${
            lightOn ? 'bg-yellow-400 shadow-lg shadow-yellow-400/50' : 'bg-gray-300'
          }`}>
            <Power className={`w-10 h-10 ${
              lightOn ? 'text-white' : 'text-gray-500'
            }`} />
          </div>
          <p className="mt-2 text-sm font-semibold text-gray-600">
            {lightOn ? 'Light ON' : 'Light OFF'}
          </p>
        </div>
        <button
          onClick={() => handleLightSwitch(true)}
          className={`px-8 py-4 rounded-lg font-bold text-lg transition-all ${
            lightOn
              ? 'bg-yellow-500 text-white shadow-lg scale-105'
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
        >
          ON
        </button>
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
        value={data.status.toUpperCase()}
        alert={data.status}
      />
    </div>

    {/* Alert Summary */}
    {(data.abnormal_movement || data.sound_alert || data.button || !data.person_present) && (
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
          {!data.person_present && (
            <li className="text-red-700 font-medium">⚠ No person detected</li>
          )}
        </ul>
      </div>
    )}
  </>
);

const HistoryPage = ({ history, formatFullDate }) => (
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
                    No historical data yet. Data will appear as it&apos;s collected...
                  </td>
                </tr>
              ) : (
                history.map((entry, index) => (
                  <tr
                    key={index}
                    className={`hover:bg-gray-50 ${
                      entry.status === 'EMERGENCY' ? 'bg-red-50'
                        : entry.status === 'WARNING'? 'bg-yellow-50'
                        : ''
                    }`}
                  >
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                      {formatFullDate(entry.ts || entry.timestamp)}
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
                          }[entry.status] || 'bg-gray-100 text-gray-800'
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
    status: 'NORMAL',
    esp32_online: false,
    pi_control_enabled: true
  });

  const [history, setHistory] = useState([]);
  
  const [deviceStatus, setDeviceStatus] = useState({
    esp32_online: false,
    pi_online: false,
    esp32_control: true,
    pi_control: true
  });

  const [lightOn, setLightOn] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  // Use useRef to persist WebSocket across re-renders
  const wsRef = React.useRef(null);
  const reconnectTimerRef = React.useRef(null);
  const isMountedRef = React.useRef(true);

  // WebSocket connection for real-time updates
  useEffect(() => {
    isMountedRef.current = true;

    const connect = () => {
      if (!isMountedRef.current) return;
      
      // Clean up closed connections
      if (wsRef.current) {
        const state = wsRef.current.readyState;
        if (state === WebSocket.CONNECTING || state === WebSocket.OPEN) {
          console.log('[WebSocket] Already connected or connecting, skipping...');
          return;
        }
        // Close and clear if CLOSING or CLOSED
        if (state === WebSocket.CLOSING || state === WebSocket.CLOSED) {
          wsRef.current = null;
        }
      }
      
      const wsUrl = `ws://${window.location.hostname}:8000/ws`;
      console.log('[WebSocket] Attempting to connect to:', wsUrl);
      
      try {
        wsRef.current = new WebSocket(wsUrl);
        console.log('[WebSocket] WebSocket object created, readyState:', wsRef.current.readyState);

        wsRef.current.onopen = () => {
          console.log('[WebSocket] Connected successfully!');
          setWsConnected(true);
        };

        wsRef.current.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            console.log('[WebSocket] Received:', message.type);
            
            if (message.type === 'sensor_data') {
              const json = message.data;
              setData({
                timestamp: json.timestamp || json.ts,
                temperature: json.temperature,
                humidity: json.humidity,
                button: Boolean(json.button),
                abnormal_movement: Boolean(json.abnormal_movement),
                sound_alert: Boolean(json.sound_alert),
                person_present: Boolean(json.person_present),
                status: json.status || 'NORMAL',
                esp32_online: Boolean(json.esp32_online),
                pi_control_enabled: Boolean(json.pi_control_enabled)
              });
            } else if (message.type === 'device_status') {
              console.log('[WebSocket] Device status:', message.data);
              setDeviceStatus(message.data);
            }
          } catch (error) {
            console.error('[WebSocket] Error parsing message:', error);
          }
        };

        wsRef.current.onclose = (event) => {
          console.log('[WebSocket] Connection closed. Code:', event.code, 'Reason:', event.reason);
          setWsConnected(false);
          
          // Reconnect if not normal closure and still mounted
          if (isMountedRef.current && event.code !== 1000) {
            console.log('[WebSocket] Will reconnect in 3s...');
            reconnectTimerRef.current = setTimeout(connect, 3000);
          }
        };

        wsRef.current.onerror = (error) => {
          console.error('[WebSocket] Connection error:', error);
        };
      } catch (error) {
        console.error('[WebSocket] Failed to create WebSocket:', error);
        if (isMountedRef.current) {
          reconnectTimerRef.current = setTimeout(connect, 3000);
        }
      }
    };

    // Initial connection
    connect();

    // Cleanup function
    return () => {
      console.log('[WebSocket] Component unmounting, cleaning up...');
      isMountedRef.current = false;
      
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      
      if (wsRef.current) {
        const state = wsRef.current.readyState;
        if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
          wsRef.current.close(1000, 'Component unmounted');
        }
        wsRef.current = null;
      }
    };
  }, []);

  // Fetch history only when on history page (every 5 seconds)
  useEffect(() => {
    if (currentPage !== 'history') return;

    const fetchHistory = async () => {
      try {
        const res = await fetch(`http://${window.location.hostname}:8000/api/history`);
        const json = await res.json();
        setHistory(json);
      } catch (error) {
        console.error("Error fetching history:", error);
      }
    };

    fetchHistory();
    const interval = setInterval(fetchHistory, 5000);
    return () => clearInterval(interval);
  }, [currentPage]);

  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    // Handle both ISO string and SQLite datetime format
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      // Try parsing SQLite format: "YYYY-MM-DD HH:MM:SS"
      const [datePart, timePart] = timestamp.split(' ');
      if (datePart && timePart) {
        return timePart;
      }
      return timestamp;
    }
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      hour12: false 
    });
  };

  const formatFullDate = (timestamp) => {
    if (!timestamp) return 'N/A';
    // Handle both ISO string and SQLite datetime format
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      // SQLite format is already human-readable: "YYYY-MM-DD HH:MM:SS"
      return timestamp;
    }
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  const handleControlChange = async (device, enabled) => {
    try {
      const endpoint = device === 'esp32' 
        ? `http://${window.location.hostname}:8000/api/control/esp32?enabled=${enabled}`
        : `http://${window.location.hostname}:8000/api/control/pi?enabled=${enabled}`;
      
      const res = await fetch(endpoint, { method: 'POST' });
      const json = await res.json();
      
      if (json.success) {
        console.log(`${device.toUpperCase()} control changed to ${enabled ? 'ENABLED' : 'DISABLED'}`);
        // Update local state immediately for better UX
        setDeviceStatus(prev => ({
          ...prev,
          [`${device}_control`]: enabled
        }));
      } else {
        console.error(`Failed to change ${device} control:`, json.error);
      }
    } catch (error) {
      console.error(`Error changing ${device} control:`, error);
    }
  };

  const handleLightSwitch = async (turnOn) => {
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/control/servo?turn_on=${turnOn}`, { 
        method: 'POST' 
      });
      const json = await res.json();
      
      if (json.success) {
        setLightOn(turnOn);
        console.log(`Light switch turned ${turnOn ? 'ON' : 'OFF'}`);
      } else {
        console.error('Failed to control light switch:', json.error);
      }
    } catch (error) {
      console.error('Error controlling light switch:', error);
    }
  };

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
        {currentPage === 'dashboard' ? (
          <DashboardPage 
            data={data} 
            formatTime={formatTime} 
            deviceStatus={deviceStatus}
            onControlChange={handleControlChange}
            lightOn={lightOn}
            handleLightSwitch={handleLightSwitch}
            wsConnected={wsConnected}
          />
        ) : (
          <HistoryPage history={history} formatFullDate={formatFullDate} />
        )}
      </div>
    </div>
  );
}