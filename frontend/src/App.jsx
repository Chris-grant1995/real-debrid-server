import { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [magnetLink, setMagnetLink] = useState('');
  const [torrentFile, setTorrentFile] = useState(null);
  const [torrents, setTorrents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [expandedTorrentId, setExpandedTorrentId] = useState(null);
  const [torrentFiles, setTorrentFiles] = useState({}); // { torrentId: [{name, type, path}, ...] }
  const [fetchingFiles, setFetchingFiles] = useState({}); // { torrentId: true/false }

  const fetchTorrents = async (initialLoad = false) => {
    if (initialLoad) {
      setLoading(true);
    }
    setError('');
    try {
      const response = await fetch(`${import.meta.env.VITE_BACKEND_API_URL}/torrents/recent`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setTorrents(data);
    } catch (err) {
      setError(`Failed to fetch torrents: ${err.message}`);
    } finally {
      if (initialLoad) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchTorrents(true); // Initial load with loading indicator
    const interval = setInterval(() => fetchTorrents(false), 10000); // Subsequent loads without
    return () => clearInterval(interval);
  }, []);

  const handleAddMagnet = async () => {
    if (!magnetLink) {
      setError('Magnet link cannot be empty.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccessMessage('');
    try {
      const response = await fetch(`${import.meta.env.VITE_BACKEND_API_URL}/torrents/add-magnet`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ magnet: magnetLink }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setSuccessMessage(`Magnet link added successfully! Torrent ID: ${data.torrent_id}`);
      setMagnetLink('');
      fetchTorrents(); // Refresh the list
    } catch (err) {
      setError(`Failed to add magnet link: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAddFile = async () => {
    if (!torrentFile) {
      setError('Please select a torrent file.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccessMessage('');
    try {
      const formData = new FormData();
      formData.append('file', torrentFile);

      const response = await fetch(`${import.meta.env.VITE_BACKEND_API_URL}/torrents/add-file`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setSuccessMessage(`Torrent file added successfully! Torrent ID: ${data.torrent_id}`);
      setTorrentFile(null);
      fetchTorrents(); // Refresh the list
    } catch (err) {
      setError(`Failed to add torrent file: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchTorrentFiles = async (torrentId) => {
    if (torrentFiles[torrentId]) { // Already fetched
      return;
    }
    setFetchingFiles(prev => ({ ...prev, [torrentId]: true })); // Set fetching state to true
    setError('');
    try {
      const response = await fetch(`${import.meta.env.VITE_BACKEND_API_URL}/torrents/${torrentId}/files`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setTorrentFiles(prev => ({ ...prev, [torrentId]: data }));
    } catch (err) {
      setError(`Failed to fetch files for torrent ${torrentId}: ${err.message}`);
    } finally {
      setFetchingFiles(prev => ({ ...prev, [torrentId]: false })); // Set fetching state to false
    }
  };

  const handleToggleExpand = (torrentId) => {
    if (expandedTorrentId === torrentId) {
      setExpandedTorrentId(null);
    } else {
      setExpandedTorrentId(torrentId);
      fetchTorrentFiles(torrentId);
    }
  };

  const handleDeleteTorrent = async (torrentId, torrentFilename) => {
    const confirmDelete = window.confirm(`Are you sure you want to delete "${torrentFilename}"?`);
    if (!confirmDelete) {
      return;
    }

    const removeAlsoFromRD = window.confirm(`Do you also want to remove "${torrentFilename}" from Real-Debrid?`);

    setLoading(true);
    setError('');
    setSuccessMessage('');
    try {
      const response = await fetch(`${import.meta.env.VITE_BACKEND_API_URL}/torrents/${torrentId}?remove_from_rd=${removeAlsoFromRD}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }
      setSuccessMessage(`Torrent ${torrentId} deleted successfully.`);
      fetchTorrents(); // Refresh the list
    } catch (err) {
      setError(`Failed to delete torrent: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <h1>Real-Debrid UI</h1>

      <div className="form-section">
        <h2>Add Magnet Link</h2>
        <input
          type="text"
          value={magnetLink}
          onChange={(e) => setMagnetLink(e.target.value)}
          placeholder="Enter magnet link"
        />
        <button onClick={handleAddMagnet} disabled={loading}>
          {loading ? 'Adding...' : 'Add Magnet'}
        </button>
      </div>

      <div className="form-section">
        <h2>Upload Torrent File</h2>
        <input
          type="file"
          accept=".torrent"
          onChange={(e) => setTorrentFile(e.target.files[0])}
        />
        <button onClick={handleAddFile} disabled={loading}>
          {loading ? 'Uploading...' : 'Upload Torrent'}
        </button>
      </div>

      {loading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {successMessage && <p style={{ color: 'green' }}>{successMessage}</p>}

      <div className="torrents-section">
        <h2>Recent Torrents</h2>
        {torrents.length === 0 ? (
          <p>No torrents found or API key is missing/invalid.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Size</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Added Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {torrents.map((torrent) => (
                <tr key={torrent.id}>
                  <td>
                    {torrent.rclone_available ? (
                      <div>
                        <span onClick={() => handleToggleExpand(torrent.id)} style={{ cursor: 'pointer', color: '#61dafb' }}>
                          {torrent.filename} {expandedTorrentId === torrent.id ? '[-]' : '[+]'}
                        </span>
                        {torrent.rclone_available && torrent.rclone_available_timestamp && (
                          <p className="rclone-timestamp">
                            Available: {new Date(torrent.rclone_available_timestamp).toLocaleString()}
                          </p>
                        )}
                        {expandedTorrentId === torrent.id && (
                          fetchingFiles[torrent.id] ? (
                            <p>Loading files...</p>
                          ) : torrentFiles[torrent.id] && torrentFiles[torrent.id].length > 0 ? (
                            <ul className="file-list">
                              {torrentFiles[torrent.id].map((file, index) => (
                                <li key={index} className="file-item">
                                  {file.type === 'directory' ? (
                                    <span className="directory-name">{file.name}/</span>
                                  ) : (
                                    <>
                                      <span>{file.name}</span>
                                        <a
                                          href={`${import.meta.env.VITE_BACKEND_API_URL}/torrents/${torrent.id}/stream/${file.path}`}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="download-link"
                                        >
                                          Download
                                        </a>
                                    </>
                                  )}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p>No files found.</p>
                          )
                        )}
                      </div>
                    ) : (
                      torrent.filename
                    )}
                  </td>
                  <td>{(torrent.bytes / (1024 * 1024 * 1024)).toFixed(2)} GB</td>
                  <td>{torrent.status}</td>
                  <td>{torrent.progress}%</td>
                  <td>{new Date(torrent.added).toLocaleString()}</td>
                  <td>
                    <button onClick={() => handleDeleteTorrent(torrent.id, torrent.filename)} disabled={loading}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default App;
