document.addEventListener('DOMContentLoaded', function() {
    // --- Tab Navigation ---
    const statusView = document.getElementById('status-view');
    const terminalView = document.getElementById('terminal-view');
    const showStatusBtn = document.getElementById('show-status');
    const showTerminalBtn = document.getElementById('show-terminal');

    showStatusBtn.addEventListener('click', () => {
        statusView.classList.remove('hidden');
        terminalView.classList.add('hidden');
        showStatusBtn.classList.add('active');
        showTerminalBtn.classList.remove('active');
    });

    showTerminalBtn.addEventListener('click', () => {
        statusView.classList.add('hidden');
        terminalView.classList.remove('hidden');
        showStatusBtn.classList.remove('active');
        showTerminalBtn.classList.add('active');
        term.focus();
    });

    // --- Status Page Logic ---
    const statusContent = document.getElementById('status-content');
    const jammerContent = document.getElementById('jammer-content');
    const scannerTableBody = document.getElementById('scanner-table-body');

    const updateStatus = async () => {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();

            statusContent.innerHTML = `
                <p><span class="status-label">Coordinator:</span> <span class="status-value ${data.running ? 'ok' : 'error'}">${data.running ? 'RUNNING' : 'STOPPED'}</span></p>
                <p><span class="status-label">Attack Mode:</span> ${data.attack_mode || 'N/A'}</p>
                <p><span class="status-label">Scanner Device:</span> <span class="status-value ${data.scanner_connected ? 'ok' : 'error'}">${data.scanner_connected ? 'CONNECTED' : 'DISCONNECTED'}</span></p>
                <p><span class="status-label">Jammer Device:</span> <span class="status-value ${data.jammer_connected ? 'ok' : 'error'}">${data.jammer_connected ? 'CONNECTED' : 'DISCONNECTED'}</span></p>
                <p><span class="status-label">Hopping Detection:</span> <span class="status-value ${data.hopping_mode ? 'ok' : 'error'}">${data.hopping_mode ? 'ACTIVE' : 'INACTIVE'}</span></p>
            `;

            if (data.jamming && data.current_target) {
                const target = data.current_target;
                jammerContent.innerHTML = `
                    <p><span class="status-label">State:</span> <span class="status-value jamming">JAMMING</span></p>
                    <p><span class="status-label">Frequency:</span> ${typeof target.frequency === 'number' ? target.frequency.toFixed(3) + ' MHz' : target.frequency}</p>
                    <p><span class="status-label">Bandwidth:</span> ${target.bandwidth ? target.bandwidth.toFixed(2) + ' MHz' : 'N/A'}</p>
                    <p><span class="status-label">Power:</span> ${target.power ? target.power.toFixed(1) + ' dB' : 'N/A'}</p>
                    <p><span class="status-label">Band:</span> ${target.band || 'N/A'}</p>
                `;
            } else {
                jammerContent.innerHTML = '<p><span class="status-label">State:</span> <span class="status-value ok">IDLE / SCANNING</span></p>';
            }

            scannerTableBody.innerHTML = '';
            if (data.recent_detections && data.recent_detections.length > 0) {
                data.recent_detections.forEach(det => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${det.frequency.toFixed(3)}</td>
                        <td>${det.power.toFixed(1)}</td>
                        <td>${det.band}</td>
                        <td>${new Date(det.last_seen + 'Z').toLocaleTimeString()}</td>
                    `;
                    scannerTableBody.appendChild(row);
                });
            } else {
                const row = document.createElement('tr');
                row.innerHTML = '<td colspan="4">No signals detected recently...</td>';
                scannerTableBody.appendChild(row);
            }

        } catch (error) {
            console.error("Failed to fetch status:", error);
            if (statusContent) statusContent.innerHTML = '<p class="status-value error">Failed to connect to backend.</p>';
        }
    };

    // --- Terminal Logic ---
    const term = new Terminal({
        cursorBlink: true,
        theme: {
            background: '#2c2c2c',
            foreground: '#e0e0e0',
        }
    });
    term.open(document.getElementById('terminal-container'));
    
    const termSocket = io('/terminal');

    term.onData(data => {
        termSocket.emit('pty_input', { 'input': data });
    });

    termSocket.on('pty_output', data => {
        term.write(data.output);
    });

    // --- Interval ---
    // Only run the status update if the status view is visible
    if (document.getElementById('status-view')) {
        updateStatus();
        setInterval(updateStatus, 2000);
    }
});