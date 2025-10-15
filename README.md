# Reactive Jammer System

<pre>
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║               REACTIVE JAMMER SYSTEM                      ║
    ║                                                           ║
    ║             Scan - Detect - Jam - Adapt                   ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
</pre>

## Legal Disclaimer

**WARNING: The use of this software for jamming or interfering with radio communications is illegal in most countries.** This project is intended for educational and research purposes only. Users are solely responsible for complying with all applicable laws and regulations in their jurisdiction. The developers of this project do not condone any illegal use of this software and are not responsible for any damages or legal issues that may arise from its use.

## Overview

The Reactive Jammer System is a sophisticated, next-generation SDR (Software-Defined Radio) application designed for intelligent, real-time detection and neutralization of radio frequency signals. It uses one SDR for scanning and a second for jamming, orchestrated by a central coordinator with an intelligent targeting engine.

The system is controlled through a comprehensive, redesigned web interface that provides real-time data visualization, dynamic system control, and direct terminal access. Its new simulation engine allows for robust testing of all features without any hardware.

## Key Features

- **Intelligent Targeting Engine:** The system no longer just jams the first or strongest signal. A new **Threat Score** system analyzes and prioritizes all detected signals based on power, persistence, and hopping behavior, ensuring the jammer is always focused on the most significant threat.

- **Redesigned Web Interface (Bootstrap 5):** The UI has been completely overhauled for a modern, responsive, and more intuitive user experience.

- **Advanced Dynamic Controls:**
    - **Interactive Targeting:** Click any signal in the "Detected Signals" list to immediately jam it.
    - **Dynamic Mode Switching:** Change the Attack Mode (Targeted, Wide-Band) and Scan Mode (Priority, Sequential, Random) on the fly without a restart.
    - **Live Band Selection:** Interactively select and de-select which frequency bands are actively scanned.
    - **Manual Wide-Band Attack:** Choose any band from a dropdown and instantly launch a wide-band attack.

- **Thorough Scanning:** The scanning algorithm has been upgraded from a sparse check to a continuous sweep, ensuring no signals are missed within a targeted band.

- **Interactive Web Terminal:** An integrated, full-featured terminal (Xterm.js) in the web UI provides direct shell access to the host machine for advanced users.

- **Dynamic Simulation Mode:** The `--simulate` flag now launches a high-fidelity simulation.
    - A `SignalGenerator` creates a dynamic RF environment with multiple signals, including frequency hoppers.
    - The simulation provides a **closed-loop feedback system**: jamming a signal in the UI will cause it to disappear from the spectrum analyzer, visually confirming the system is working.

- **Predictive Frequency Hopping:** Records and analyzes hopping patterns to predict a signal's next frequency, allowing for near-instantaneous re-acquisition and jamming.

- **Extensive Frequency Database:** Comes pre-configured with a wide range of common frequency bands, including IoT (915/868/433 MHz), WiFi, Cellular (5G/LTE), GPS, and more.

## System & Hardware Requirements

### Recommended Operating System
- **Debian-based Linux:** Ubuntu 22.04+, Kali Linux, or similar distributions are recommended, as the installation guide is tailored for the `apt` package manager.

### Hardware
- **Live Mode:**
    - 2 x HackRF One (or other `pyhackrf`-compatible SDRs). One device is required for scanning and one for jamming.
- **Simulation Mode:**
    - No SDR hardware is required.

### Software
- Python 3.10+

## Installation Guide

These steps will guide you through a complete setup on a fresh Debian-based system.

**1. Install System Dependencies:**
Open a terminal and run the following command to install Python's virtual environment tools and the necessary HackRF libraries.
```bash
sudo apt update
sudo apt install python3.13-venv hackrf libhackrf-dev
```

**2. Create the Python Virtual Environment:**
Navigate to the `reactive-jammer` project directory and create a virtual environment.
```bash
cd path/to/reactive-jammer
python3 -m venv venv
```

**3. Activate the Virtual Environment:**
You must activate the environment every time you open a new terminal to work on the project.
```bash
source venv/bin/activate
```
Your terminal prompt will change to show `(venv)`.

**4. Install All Python Packages:**
With the environment active, install all the required Python libraries from the `requirements.txt` file.
```bash
pip install -r requirements.txt
```

## Usage Instructions

Ensure your virtual environment is activated (`source venv/bin/activate`) before running the application.

**1. Running in Simulation Mode (No Hardware Needed):**
This is the best way to test the software and user interface.
```bash
python3 main.py --simulate
```

**2. Running in Live Mode (With HackRFs):**
Connect your two HackRF devices. The script may require root permissions to access USB hardware.
```bash
sudo python3 main.py
```

**3. Using Different Attack Modes:**
- **Targeted Mode (Default):**
  ```bash
  sudo python3 main.py
  ```
- **Wide-Band Attack Mode:**
  ```bash
  sudo python3 main.py --attack-mode wide_band
  ```

**4. Access the Web Interface:**
Once the script is running, open your web browser and navigate to:
**`http://localhost:5000`**

## Troubleshooting

- **`pip install` fails:**
  - Ensure your virtual environment is active. Your terminal prompt must start with `(venv)`.
  - Ensure you have run `sudo apt update` and installed the system dependencies from the installation guide.

- **`hackrf_error` or "Device not found" at runtime:**
  - Make sure your HackRFs are plugged in securely.
  - Run the command `hackrf_info` in your terminal. If it doesn't show your devices, there may be a system-level issue with your HackRF installation or USB drivers.
  - Try running the script with `sudo`, as it's often required for hardware access.

## For Developers: Extending the Project

This project is designed to be modular and extensible.

- **File Structure:**
    - `main.py`: Main application entry point.
    - `config.py`: All settings, including frequency bands and device gains.
    - `coordinator.py`: The central logic orchestrating the scanner and jammer.
    - `scanner.py`: Handles signal detection and database logging.
    - `jammer.py`: Manages the jamming hardware and transmission logic.
    - `web_ui.py`: The Flask and Socket.IO backend for the web interface.
    - `fake_hackrf.py`: The simulated SDR used in `--simulate` mode.

- **Adding New Frequency Bands:**
  - Simply edit the `TARGET_FREQUENCIES` dictionary in `config.py`.

- **Improving Hopping Prediction:**
  - The core logic is in the `_predict_next_hop` method in `coordinator.py`. This could be enhanced with more advanced pattern recognition algorithms (e.g., sequence analysis).

- **Adding New Jamming Techniques:**
  - The `_jam_loop` (for targeted tones), `_transmit_noise_jamming`, and `_wideband_jam_loop` methods in `jammer.py` can be modified to implement different jamming waveforms.

## Contributing

Developers are more than welcome to help develop this into a more robust and advanced system. Feel free to fork the project, create feature branches, and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.
