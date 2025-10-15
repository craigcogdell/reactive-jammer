"""
Configuration settings for the reactive jammer system.
"""

# Target frequency ranges in MHz
TARGET_FREQUENCIES = {
    # ISM Bands
    "ISM_433": {"start": 433.05, "end": 434.79, "description": "433MHz ISM Band (LoRa, IoT)"},
    "ISM_868": {"start": 868.0, "end": 868.6, "description": "868MHz ISM Band (LoRa, Sigfox Europe)"},
    "ISM_915": {"start": 902.0, "end": 928.0, "description": "915MHz ISM Band (LoRa, Sigfox US)"},

    # WiFi/BT/Zigbee
    "WIFI_2_4": {"start": 2400.0, "end": 2500.0, "description": "2.4GHz WiFi, Bluetooth, Zigbee"},
    "WIFI_5": {"start": 5150.0, "end": 5850.0, "description": "5GHz WiFi"},
    
    # Cellular Bands (Common Sub-6GHz 5G/LTE)
    "CELLULAR_LOW": {"start": 600.0, "end": 960.0, "description": "Low-Band Cellular (5G/LTE)"},
    "CELLULAR_MID": {"start": 1710.0, "end": 2200.0, "description": "Mid-Band Cellular (5G/LTE)"},
    "CELLULAR_HIGH": {"start": 2300.0, "end": 2700.0, "description": "High-Band Cellular (5G/LTE/BRS)"},
    "CELLULAR_CBRS": {"start": 3550.0, "end": 3700.0, "description": "CBRS Band (5G/LTE)"},
    "CELLULAR_C_BAND": {"start": 3700.0, "end": 3980.0, "description": "C-Band (5G)"},

    # GPS/GNSS Bands
    "GPS_L1": {"start": 1574.42, "end": 1576.42, "description": "GPS L1"},
    "GPS_L2": {"start": 1226.60, "end": 1228.60, "description": "GPS L2"},

    # Other bands
    "BROADCAST_FM": {"start": 87.5, "end": 108.0, "description": "Broadcast FM Radio"},
    "AIRBAND": {"start": 108.0, "end": 137.0, "description": "Civilian Aircraft Communication"},
    "MICROWAVE_OVEN": {"start": 2450.0, "end": 2460.0, "description": "Microwave Oven Leakage"}
}

# Device indices
SCANNER_DEVICE_INDEX = 0
JAMMER_DEVICE_INDEX = 1

# HackRF device settings - now a list
HACKRF_SETTINGS = [
    # Device 0 (Scanner)
    {
        "sample_rate": 20e6,
        "lna_gain": 32,
        "vga_gain": 28,
        "txvga_gain": 0, # Not used for scanning
        "freq_correction": 0
    },
    # Device 1 (Jammer)
    {
        "sample_rate": 20e6,
        "lna_gain": 0, # Not used for jamming
        "vga_gain": 0, # Not used for jamming
        "txvga_gain": 47, # Max for transmission
        "freq_correction": 0
    }
]

# Jammer-specific settings
JAMMER_SETTINGS = {
    "amplitude": 0.9, # Amplitude of jamming signal (0.0-1.0)
    "attack_mode": "targeted" # Options: targeted, wide_band
}

# Scanner settings
SCANNER_SETTINGS = {
    "fft_size": 1024,         # FFT size for spectrum analysis
    "integration_time": 0.1,  # Integration time in seconds
    "threshold": -70,         # Signal detection threshold in dBm
    "min_signal_bw": 0.1,     # Minimum signal bandwidth in MHz
    "max_signal_bw": 20.0,    # Maximum signal bandwidth in MHz
    "scan_interval": 0.05,    # Time between scans in seconds
    "hop_detection_window": 5 # Number of samples to detect frequency hopping
}

# Database settings
DATABASE_SETTINGS = {
    "db_file": "detected_frequencies.db",
    "table_name": "frequencies",
    "history_limit": 1000     # Maximum number of historical entries to keep
}

# General settings
GENERAL_SETTINGS = {
    "log_level": "INFO",
    "log_file": "reactive_jammer.log",
    "priority_frequencies": ["ISM_915", "WIFI_2_4", "CELLULAR_LOW"],  # Check these first
    "scan_mode": "priority_first",  # Options: priority_first, sequential, random
    "attack_mode": "targeted" # Options: targeted, wide_band
}