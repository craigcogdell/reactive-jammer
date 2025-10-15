import numpy as np
import time

class FakeHackRF:
    """A fake HackRF device that interacts with a shared SimulationState."""
    def __init__(self, device_index=None, serial_number=None, simulation_state=None):
        self.center_freq = 100e6
        self.sample_rate = 20e6
        self.txvga_gain = 47
        self.lna_gain = 32
        self.vga_gain = 28
        self._is_transmitting = False
        self.simulation_state = simulation_state
        self.is_scanner = (device_index == 0) # Simple way to differentiate roles
        print(f"Initialized FakeHackRF for {'Scanner' if self.is_scanner else 'Jammer'}")

    def close(self):
        print(f"FakeHackRF for {'Scanner' if self.is_scanner else 'Jammer'} closed.")

    def read_samples(self, num_samples):
        """Generate simulated samples based on the shared simulation state."""
        # Base noise
        samples = (np.random.normal(0, 0.05, num_samples) + 1j * np.random.normal(0, 0.05, num_samples)).astype(np.complex64)

        if not self.simulation_state:
            return samples

        # Get current jammer status from the shared state
        jammer_active, jammer_freq, jammer_bw = self.simulation_state.get_jammer_status()

        # Get signals from shared state
        signals_to_generate = self.simulation_state.get_signals()

        for signal in signals_to_generate:
            is_jammed = False
            if jammer_active:
                # Check if the signal frequency falls within the jammer's bandwidth
                jam_start = jammer_freq - (jammer_bw / 2)
                jam_end = jammer_freq + (jammer_bw / 2)
                if jam_start <= signal.freq_mhz <= jam_end:
                    is_jammed = True
            
            # If the signal is not jammed, add it to the samples
            if not is_jammed:
                freq_offset = (signal.freq_mhz * 1e6) - self.center_freq
                # Only generate signal if it's within the scanner's current view
                if abs(freq_offset) < self.sample_rate / 2:
                    t = np.arange(num_samples) / self.sample_rate
                    # Power scaling (very approximate)
                    amplitude = 10**((signal.power_dbm) / 20) * 5 # Magic number for visibility
                    
                    # Simple wide-band noise for signals with more bandwidth
                    if signal.bandwidth_mhz > 0.3:
                        noise = (np.random.normal(0, 1, num_samples) + 1j*np.random.normal(0,1,num_samples))
                        signal_wave = amplitude * noise * np.exp(2j * np.pi * freq_offset * t)
                    else: # Simple tone for narrow-band
                        signal_wave = amplitude * np.exp(2j * np.pi * freq_offset * t)

                    samples += signal_wave.astype(np.complex64)

        return samples

    def tx(self, samples):
        """Simulate transmitting by updating the shared simulation state."""
        if self.simulation_state and not self.is_scanner:
            # The jammer FakeHackRF updates the state
            center_freq_mhz = self.center_freq / 1e6
            # Approximate bandwidth from the type of samples (noise vs tone)
            # This is a simplification; in reality, the coordinator sets this.
            # For the simulation, we'll assume the coordinator sets it correctly.
            # Here we just notify the state that the jammer is active.
            # The actual bandwidth is passed in start_jamming.
            # We'll let the coordinator handle the state update for simplicity.
            pass

    def start_rx_mode(self, callback):
        pass

    def stop_rx_mode(self):
        pass