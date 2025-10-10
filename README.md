<!-- Hero image section -->
<p align="center">
  <img src="./static/hero.png" alt="Reactive Jammer Hero" width="100%" style="max-height:360px; object-fit:cover;">
</p>

<h1 align="center">Reactive Jammer</h1>

<p align="center">
  <em>Reactive Jammer using two HackRF SDR radios with a GUI interface</em>
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-green.svg">
  <img alt="Status" src="https://img.shields.io/badge/status-Active-success.svg">
</p>


# Reactive Jammer System

<pre>
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║               REACTIVE JAMMER SYSTEM                      ║
    ║                                                           ║
    ║  Scan - Detect - Jam - Adapt                              ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
</pre>

## Overview

The Reactive Jammer System is a sophisticated SDR (Software-Defined Radio) application designed for detecting and neutralizing radio frequency signals in real-time. It uses one SDR for scanning the spectrum and a second for targeted jamming. The system is equipped with a web-based user interface for monitoring and control, predictive algorithms for tracking frequency-hopping signals, and multiple attack modes.

## Key Features

- **Dual SDR Operation:** Utilizes two separate SDRs for simultaneous scanning and jamming, ensuring no interruption in detection.
- **Multiple Attack Modes:**
    - **Targeted Attack:** Reactively detects, analyzes, and jams specific, active signals.
    - **Wide-Band Attack:** Proactively jams an entire frequency band with a sweeping noise signal.
- **Predictive Frequency Hopping:** Records and analyzes hopping patterns to predict a signal's next frequency, allowing for near-instantaneous re-acquisition and jamming.
- **Web-Based UI:** A comprehensive dashboard accessible at `http://localhost:5000` for real-time monitoring of system status, device connections, detected signals, and active jamming targets.
- **Interactive Web Terminal:** An integrated, full-featured terminal in the web UI provides direct shell access to the host machine for advanced users.
- **Simulation Mode:** Run the entire application without any hardware using the `--simulate` flag. Perfect for development, testing, and demonstration.
- **Extensive Frequency Database:** Comes pre-configured with a wide range of common frequency bands, including ISM, WiFi, Cellular (5G/LTE), GPS, and more.

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

## Notice

The Reactive Jammer is a brilliant concept — I don't yet have the two HackRFs needed to test it, so it may have issues. I'll be spending more time building the system; for now let's class it as a prototype. If anyone is interested in helping develop this into a real-world, lab-safe application or wants to collaborate, please feel free to reach out. (Note: this work is intended for controlled, legal research/testing only.)

<!-- Buy Me A Drink (SVG button stored in ./.static/buymeacoffee.svg) --> <p align="center"> <a href="https://www.buymeacoffee.com/craigcogdey" target="_blank" rel="noopener noreferrer" aria-label="Buy me a drink"> <img src="./static/buymeacoffee.svg" alt="Buy Me a Drink" width="220" style="max-height:72px;"> </a> </p>
