import numpy as np
import time

class FakeHackRF:
    """A fake HackRF device for simulation purposes."""
    def __init__(self, device_index=None, serial_number=None):
        self.center_freq = 100e6
        self.sample_rate = 20e6
        self.lna_gain = 32
        self.vga_gain = 30
        self.txvga_gain = 47
        self._is_transmitting = False
        self._simulated_signal_freq = 915e6  # A signal to be "found"
        self._simulated_signal_bw = 0.5e6
        print("Initialized FakeHackRF")

    def close(self):
        print("FakeHackRF closed.")

    def read_samples(self, num_samples):
        """Generate simulated samples with a fake signal."""
        # Generate base noise
        i_samples = np.random.normal(0, 0.1, num_samples)
        q_samples = np.random.normal(0, 0.1, num_samples)
        samples = i_samples + 1j * q_samples

        # Add a simulated signal if it's within our current view
        freq_offset = self._simulated_signal_freq - self.center_freq
        if abs(freq_offset) < self.sample_rate / 2:
            t = np.arange(num_samples) / self.sample_rate
            signal = 0.5 * np.exp(2j * np.pi * freq_offset * t)
            
            # Add some simple bandwidth by modulating the signal
            bw_mod = np.sin(2 * np.pi * (self._simulated_signal_bw / 4) * t)
            signal *= bw_mod

            samples += signal

        return samples.astype(np.complex64)

    def tx(self, samples):
        """Simulate transmitting."""
        if not self._is_transmitting:
            self._is_transmitting = True
        # In a real simulation, we might do something here, but for now, just pass.
        pass

    # Add other methods and properties to mimic the real API
    def start_rx_mode(self, callback):
        pass

    def stop_rx_mode(self):
        pass
