document.addEventListener('DOMContentLoaded', () => {
    // --- Sockets --- 
    const socket = io();
    const logSocket = io('/logs');
    const termSocket = io('/terminal');

    // --- DOM Elements ---
    const scannerStatus = document.getElementById('scanner-status');
    const jammerStatus = document.getElementById('jammer-status');
    const jammingState = document.getElementById('jamming-state');
    const currentTarget = document.getElementById('current-target');
    const detectedList = document.getElementById('detected-list');
    const logContainer = document.getElementById('log-container');
    const manualFreq = document.getElementById('manual-freq');
    const manualBw = document.getElementById('manual-bw');
    const startJamBtn = document.getElementById('start-jam-btn');
    const stopJamBtn = document.getElementById('stop-jam-btn');
    const attackModeSelect = document.getElementById('attack-mode-select');
    const scanModeSelect = document.getElementById('scan-mode-select');
    const settingsModal = document.getElementById('settingsModal');
    const jammerIndexInput = document.getElementById('jammer-index-input');
    const saveConfigBtn = document.getElementById('save-config-btn');
    const scanBandsList = document.getElementById('scan-bands-list');
    const wideBandSelect = document.getElementById('wide-band-select');
    const startWideBandBtn = document.getElementById('start-wide-band-btn');

    // --- Xterm.js Setup ---
    const term = new Terminal({
        convertEol: true,
        fontFamily: `'Roboto Mono', monospace`,
        theme: {
            background: '#1a1b26',
            foreground: '#c0caf5',
            cursor: '#c0caf5',
            selection: '#414868'
        }
    });
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(document.getElementById('terminal'));
    fitAddon.fit();
    window.addEventListener('resize', () => fitAddon.fit());

    // --- Chart.js Setup ---
    const ctx = document.getElementById('spectrum-chart').getContext('2d');
    const spectrumChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Spectrum (dBm)',
                data: [],
                borderColor: '#7aa2f7',
                backgroundColor: 'rgba(122, 162, 247, 0.1)',
                borderWidth: 1,
                pointRadius: 0,
                tension: 0.4
            }]
        },
        options: {
            animation: false,
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'linear',
                    title: { display: true, text: 'Frequency (MHz)', color: '#a9b1d6' },
                    ticks: { color: '#c0caf5' },
                    grid: { color: '#414868' }
                },
                y: {
                    title: { display: true, text: 'Power (dBm)', color: '#a9b1d6' },
                    min: -100,
                    max: 0,
                    ticks: { color: '#c0caf5' },
                    grid: { color: '#414868' }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });

    // --- API Communication ---
    async function apiPost(endpoint, body) {
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (!response.ok) {
                console.error(`API Error: ${response.statusText}`);
            }
            return response.json();
        } catch (error) {
            console.error(`Fetch Error: ${error}`);
        }
    }

    // --- UI Update Function ---
    function updateStatus() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                // Status lights
                scannerStatus.classList.toggle('green', data.scanner_connected);
                jammerStatus.classList.toggle('green', data.jammer_connected);

                // System info
                if (!attackModeSelect.dataset.initialized) {
                    // Populate mode selects once on first load
                    ['targeted', 'wide_band'].forEach(mode => {
                        const option = new Option(mode.replace('_', ' ').toUpperCase(), mode);
                        if (mode === data.attack_mode) option.selected = true;
                        attackModeSelect.add(option);
                    });
                    ['priority_first', 'sequential', 'random'].forEach(mode => {
                        const option = new Option(mode.replace('_', ' ').toUpperCase(), mode);
                        if (mode === data.scan_mode) option.selected = true;
                        scanModeSelect.add(option);
                    });
                    attackModeSelect.dataset.initialized = true;
                }

                jammingState.textContent = data.jamming ? 'ACTIVE' : 'INACTIVE';
                jammingState.className = data.jamming ? 'badge bg-danger' : 'badge bg-success';

                // Target info
                if (data.current_target) {
                    const target = data.current_target;
                    currentTarget.textContent = `${target.frequency.toFixed(2)} MHz @ ${target.bandwidth.toFixed(2)} MHz BW`;
                } else {
                    currentTarget.textContent = 'None';
                }

                // Detected list
                detectedList.innerHTML = '';
                const listGroup = document.createElement('div');
                listGroup.className = 'list-group';

                data.recent_detections.forEach(det => {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'list-group-item list-group-item-action';
                    button.innerHTML = `<strong>${det.frequency.toFixed(2)} MHz</strong> | ${det.power.toFixed(1)} dBm | ${det.band}`;
                    button.addEventListener('click', () => {
                        apiPost('/api/jammer/set_target', { frequency: det.frequency, bandwidth: det.bandwidth });
                    });
                    listGroup.appendChild(button);
                });
                detectedList.appendChild(listGroup);

                // Spectrum chart
                if (data.spectrum_data && data.spectrum_data.frequencies) {
                    const { frequencies, psd } = data.spectrum_data;
                    spectrumChart.data.labels = frequencies.map(f => (f / 1e6).toFixed(2));
                    spectrumChart.data.datasets[0].data = psd;
                    spectrumChart.update();
                }
            })
            .catch(error => console.error('Error fetching status:', error));
    }

    function populateBandControls() {
        fetch('/api/system/bands')
            .then(res => res.json())
            .then(data => {
                if (!data.bands) return;

                // Populate Scan Bands Checkboxes
                data.bands.forEach(band => {
                    const formCheck = document.createElement('div');
                    formCheck.className = 'form-check form-check-inline';
                    const input = document.createElement('input');
                    input.className = 'form-check-input';
                    input.type = 'checkbox';
                    input.value = band.name;
                    input.id = `check-${band.name}`;
                    input.checked = band.is_priority;
                    input.addEventListener('change', handleScanBandChange);
                    const label = document.createElement('label');
                    label.className = 'form-check-label';
                    label.htmlFor = `check-${band.name}`;
                    label.textContent = band.name;

                    formCheck.appendChild(input);
                    formCheck.appendChild(label);
                    scanBandsList.appendChild(formCheck);
                });

                // Populate Wide-Band Select
                data.bands.forEach(band => {
                    const option = new Option(band.name, band.name);
                    wideBandSelect.add(option);
                });
            });
    }

    function handleScanBandChange() {
        const selectedBands = Array.from(scanBandsList.querySelectorAll('input:checked')).map(input => input.value);
        apiPost('/api/system/scan_bands', { bands: selectedBands });
    }

    // --- Socket.IO Handlers ---
    logSocket.on('log_entry', (data) => {
        const logEntry = document.createElement('div');
        logEntry.textContent = data.log;
        logContainer.appendChild(logEntry);
        logContainer.scrollTop = logContainer.scrollHeight;
    });

    termSocket.on('pty_output', (data) => {
        term.write(data.output);
    });

    term.onData((data) => {
        termSocket.emit('pty_input', { 'input': data });
    });

    // --- Event Listeners ---
    startJamBtn.addEventListener('click', () => {
        const freq = parseFloat(manualFreq.value);
        const bw = parseFloat(manualBw.value);
        if (!freq || freq <= 0) {
            alert('Please enter a valid frequency.');
            return;
        }
        apiPost('/api/jammer/start', { frequency: freq, bandwidth: bw || 1.0 });
    });

    stopJamBtn.addEventListener('click', () => {
        apiPost('/api/jammer/stop', {});
    });

    attackModeSelect.addEventListener('change', (e) => {
        apiPost('/api/system/mode', { attack_mode: e.target.value });
    });

    scanModeSelect.addEventListener('change', (e) => {
        apiPost('/api/system/mode', { scan_mode: e.target.value });
    });

    // Settings Modal Logic
    settingsModal.addEventListener('show.bs.modal', () => {
        fetch('/api/config')
            .then(res => res.json())
            .then(data => {
                if(data.SCANNER_DEVICE_INDEX !== undefined) {
                    scannerIndexInput.value = data.SCANNER_DEVICE_INDEX;
                }
                if(data.JAMMER_DEVICE_INDEX !== undefined) {
                    jammerIndexInput.value = data.JAMMER_DEVICE_INDEX;
                }
            });
    });

    saveConfigBtn.addEventListener('click', () => {
        const newConfig = {
            'SCANNER_DEVICE_INDEX': parseInt(scannerIndexInput.value, 10),
            'JAMMER_DEVICE_INDEX': parseInt(jammerIndexInput.value, 10)
        };

        apiPost('/api/config', newConfig)
            .then(() => {
                const modal = bootstrap.Modal.getInstance(settingsModal);
                modal.hide();
                // Optionally, show a success toast/notification
                alert('Settings saved! Please restart the application for device changes to take effect.');
            });
    });

    startWideBandBtn.addEventListener('click', () => {
        const bandName = wideBandSelect.value;
        if (bandName) {
            apiPost('/api/jammer/wide_band_start', { band_name: bandName });
        }
    });

    // --- Initial Load & Interval ---
    populateBandControls();
    updateStatus();
    setInterval(updateStatus, 2000);
});
