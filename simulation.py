import threading
import time
import random
import numpy as np
from collections import deque
from config import TARGET_FREQUENCIES

class SimulatedSignal:
    """Represents a single signal in the simulated RF environment."""
    def __init__(self, freq_mhz, bandwidth_mhz, power_dbm, signal_type='static', hop_pattern=None, ttl=None):
        self.freq_mhz = freq_mhz
        self.bandwidth_mhz = bandwidth_mhz
        self.power_dbm = power_dbm
        self.signal_type = signal_type # 'static', 'hopping'
        self.hop_pattern = hop_pattern if hop_pattern else []
        self.hop_index = 0
        self.last_hop_time = time.time()
        self.hop_interval = 2.0 # seconds
        self.ttl = ttl # Time-to-live in seconds
        self.is_dead = False

    def update(self):
        """Update signal properties, e.g., for hopping or TTL."""
        if self.ttl is not None:
            self.ttl -= 0.1 # Corresponds to the sleep time in the generator
            if self.ttl <= 0:
                self.is_dead = True

        if self.signal_type == 'hopping' and self.hop_pattern:
            if time.time() - self.last_hop_time > self.hop_interval:
                self.hop_index = (self.hop_index + 1) % len(self.hop_pattern)
                self.freq_mhz = self.hop_pattern[self.hop_index]
                self.last_hop_time = time.time()
        if self.signal_type == 'hopping' and self.hop_pattern:
            if time.time() - self.last_hop_time > self.hop_interval:
                self.hop_index = (self.hop_index + 1) % len(self.hop_pattern)
                self.freq_mhz = self.hop_pattern[self.hop_index]
                self.last_hop_time = time.time()

class SimulationState:
    """Thread-safe class to manage the state of the simulated RF environment."""
    def __init__(self):
        self.signals = []
        self.jammer_active = False
        self.jammer_freq_mhz = 0
        self.jammer_bw_mhz = 0
        self.lock = threading.Lock()

    def add_signal(self, signal):
        with self.lock:
            self.signals.append(signal)

    def get_signals(self):
        with self.lock:
            return list(self.signals)

    def update_jammer(self, active, freq_mhz, bw_mhz):
        with self.lock:
            self.jammer_active = active
            self.jammer_freq_mhz = freq_mhz
            self.jammer_bw_mhz = bw_mhz

    def get_jammer_status(self):
        with self.lock:
            return self.jammer_active, self.jammer_freq_mhz, self.jammer_bw_mhz

    def update_signals(self):
        with self.lock:
            for signal in self.signals:
                signal.update()
            # Remove dead signals
            self.signals = [s for s in self.signals if not s.is_dead]

class SignalGenerator(threading.Thread):
    """A thread that dynamically adds and modifies signals in the simulation state."""
    def __init__(self, state, running_flag):
        super().__init__()
        self.state = state
        self.running = running_flag
        self.daemon = True

    def run(self):
        # Pre-defined hopping sequence for testing
        hop_pattern = [915.0, 917.5, 920.0, 922.5, 925.0]
        hopping_signal = SimulatedSignal(915.0, 0.5, -40, 'hopping', hop_pattern)
        self.state.add_signal(hopping_signal)

        # A static signal
        static_signal = SimulatedSignal(433.92, 0.2, -55, 'static')
        self.state.add_signal(static_signal)

        while self.running.is_set():
            self.state.update_signals()
            time.sleep(0.1)

    def generate_transient_signal(self, band_name):
        """Generates a temporary signal within the specified band."""
        if band_name not in TARGET_FREQUENCIES:
            return
        
        band_data = TARGET_FREQUENCIES[band_name]
        if isinstance(band_data, list):
            start_freq = band_data[0]['start']
            end_freq = band_data[-1]['end']
        else:
            start_freq = band_data['start']
            end_freq = band_data['end']
        
        # Create a signal at a random spot in the band
        freq = random.uniform(start_freq, end_freq)
        transient_signal = SimulatedSignal(freq, 1.0, -50, 'static', ttl=5.0) # Lives for 5 seconds
        self.state.add_signal(transient_signal)
