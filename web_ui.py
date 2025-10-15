
import logging
import os
import threading
import ptyprocess
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

logger = logging.getLogger('web_ui')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!_change_me'
socketio = SocketIO(app, async_mode='threading')
coordinator_ref = None
config_path = os.path.join(os.path.dirname(__file__), 'config.py')

# --- HTTP Routes ---

@app.route('/')
def index():
    """Serve the main web page."""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Provide system status as JSON for the status page."""
    if coordinator_ref:
        status = coordinator_ref.get_status()
        # Also include spectrum data if available
        status['spectrum_data'] = coordinator_ref.get_spectrum_data()
        return jsonify(status)
    return jsonify({"error": "Coordinator not initialized"}), 500

@app.route('/api/jammer/start', methods=['POST'])
def start_jammer():
    """Manually start the jammer with specified parameters."""
    if coordinator_ref:
        data = request.json
        freq = data.get('frequency')
        bw = data.get('bandwidth')
        power = data.get('power')
        if freq:
            coordinator_ref.start_jamming(freq, bw, power)
            return jsonify({"status": "Jamming started"})
        return jsonify({"error": "Frequency is required"}), 400
    return jsonify({"error": "Coordinator not initialized"}), 500

@app.route('/api/jammer/stop', methods=['POST'])
def stop_jammer():
    """Manually stop the jammer."""
    if coordinator_ref:
        coordinator_ref.stop_jamming()
        return jsonify({"status": "Jamming stopped"})
    return jsonify({"error": "Coordinator not initialized"}), 500

@app.route('/api/jammer/set_target', methods=['POST'])
def set_target():
    """Set a specific manual target for the jammer."""
    if coordinator_ref:
        data = request.json
        freq = data.get('frequency')
        bw = data.get('bandwidth')
        if freq:
            coordinator_ref.set_manual_target(freq, bw)
            return jsonify({"status": f"Manual target set to {freq} MHz"})
        return jsonify({"error": "Frequency is required"}), 400
    return jsonify({"error": "Coordinator not initialized"}), 500

@app.route('/api/system/mode', methods=['POST'])
def set_system_mode():
    """Update the system's attack or scan mode."""
    if coordinator_ref:
        data = request.json
        if 'attack_mode' in data:
            mode = data['attack_mode']
            if hasattr(coordinator_ref, 'set_attack_mode'):
                coordinator_ref.set_attack_mode(mode)
                return jsonify({"status": f"Attack mode set to {mode}"})
            return jsonify({"error": "Coordinator does not support setting attack mode"}), 501
        
        if 'scan_mode' in data:
            mode = data['scan_mode']
            if hasattr(coordinator_ref, 'set_scan_mode'):
                coordinator_ref.set_scan_mode(mode)
                return jsonify({"status": f"Scan mode set to {mode}"})
            return jsonify({"error": "Coordinator does not support setting scan mode"}), 501

        return jsonify({"error": "Invalid mode specified"}), 400
    return jsonify({"error": "Coordinator not initialized"}), 500

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    """Read or write specific settings in the config.py file."""
    if request.method == 'POST':
        try:
            new_settings = request.json
            with open(config_path, 'r') as f:
                lines = f.readlines()

            with open(config_path, 'w') as f:
                for line in lines:
                    # This is a simple parser, assumes "KEY = VALUE" format
                    if '=' in line:
                        key = line.split('=')[0].strip()
                        if key in new_settings:
                            value = new_settings[key]
                            if isinstance(value, str):
                                f.write(f"{key} = '{value}'\n")
                            else:
                                f.write(f"{key} = {value}\n")
                            continue # Move to next line after writing change
                    f.write(line)

            if coordinator_ref:
                coordinator_ref.reload_config()
            return jsonify({"status": "Configuration saved successfully"})
        except Exception as e:
            logger.error(f"Failed to write config: {e}")
            return jsonify({"error": f"Failed to write config file: {e}"}), 500

    else: # GET request
        try:
            settings = {}
            with open(config_path, 'r') as f:
                for line in f.readlines():
                    if '=' in line:
                        parts = line.split('=')
                        key = parts[0].strip()
                        value_str = parts[1].strip()
                        # Attempt to evaluate the value to its actual type
                        try:
                            settings[key] = eval(value_str)
                        except:
                            settings[key] = value_str # Store as string if eval fails
            return jsonify(settings)
        except Exception as e:
            logger.error(f"Failed to read config: {e}")
            return jsonify({"error": f"Failed to read config file: {e}"}), 500

@app.route('/api/system/bands')
def get_system_bands():
    """Return a list of all available frequency bands."""
    if coordinator_ref:
        return jsonify(coordinator_ref.get_available_bands())
    return jsonify({"error": "Coordinator not initialized"}), 500

@app.route('/api/jammer/wide_band_start', methods=['POST'])
def start_wide_band_jammer():
    """Start wide band jamming on a specific band."""
    if coordinator_ref:
        data = request.json
        band_name = data.get('band_name')
        if band_name:
            coordinator_ref.start_wideband_jamming_by_name(band_name)
            return jsonify({"status": f"Wide-band attack started on {band_name}"})
        return jsonify({"error": "band_name is required"}), 400
    return jsonify({"error": "Coordinator not initialized"}), 500

# --- WebSocket Handlers ---

# Terminal via PTY
@socketio.on('connect', namespace='/terminal')
def connect_terminal():
    logger.info("Terminal client connected")
    pty = ptyprocess.PtyProcess.spawn(['bash'])
    socketio.server.environ[request.sid]['pty'] = pty
    threading.Thread(target=read_and_forward_pty_output, args=(request.sid, pty)).start()

@socketio.on('disconnect', namespace='/terminal')
def disconnect_terminal():
    logger.info("Terminal client disconnected")
    if 'pty' in socketio.server.environ[request.sid]:
        socketio.server.environ[request.sid]['pty'].close()

@socketio.on('pty_input', namespace='/terminal')
def pty_input(data):
    if 'pty' in socketio.server.environ[request.sid]:
        socketio.server.environ[request.sid]['pty'].write(data['input'].encode())

def read_and_forward_pty_output(sid, pty):
    while pty.isalive():
        try:
            output = pty.read(1024).decode()
            socketio.emit('pty_output', {'output': output}, namespace='/terminal', room=sid)
        except (IOError, EOFError):
            break
    logger.info(f"PTY read thread for SID {sid} finished.")

# Log Streaming
class LogStreamHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        socketio.emit('log_entry', {'log': log_entry}, namespace='/logs')

@socketio.on('connect', namespace='/logs')
def connect_logs():
    logger.info("Log streaming client connected")

# --- Main Server Function ---

def run_web_server(coordinator, host='0.0.0.0', port=5000):
    """Run the Flask-SocketIO web server."""
    global coordinator_ref
    coordinator_ref = coordinator

    # Add log handler to stream logs to the web UI
    log_handler = LogStreamHandler()
    log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(log_handler)
    logging.getLogger().setLevel(logging.INFO)

    logger.info(f"Starting web UI at http://{host}:{port}")
    socketio.run(app, host=host, port=port, log_output=False)
