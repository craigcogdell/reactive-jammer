"""
Jammer module for the reactive jammer system.
Uses HackRF to transmit jamming signals on detected frequencies.
"""

import numpy as np
import time
import logging
import threading
import hackrf
from config import HACKRF_SETTINGS

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='jammer.log'
)
logger = logging.getLogger('jammer')

class Jammer:
    """HackRF jammer for transmitting signals on target frequencies."""
    
    def __init__(self, device_index=1, simulation=False):
        """Initialize the jammer with the specified HackRF device."""
        self.device_index = device_index
        self.device = None
        self.simulation = simulation
        self.sample_rate = HACKRF_SETTINGS['jammer']['sample_rate']
        self.gain = HACKRF_SETTINGS['jammer']['gain']
        self.amplitude = HACKRF_SETTINGS['jammer']['amplitude']
        
        # Jamming state
        self.current_freq = None
        self.current_bandwidth = None
        self.jamming = False
        self.jam_thread = None
        
        logger.info("Jammer initialized")
    
    def start(self):
        """Start the jammer device."""
        if self.simulation:
            from fake_hackrf import FakeHackRF
            self.device = FakeHackRF()
            logger.info("Jammer started in simulation mode.")
            return

        try:
            self.device = hackrf.HackRF(device_index=self.device_index)
            self.device.sample_rate = self.sample_rate
            self.device.txvga_gain = self.gain
            logger.info(f"Jammer device started on index {self.device_index}")
        except Exception as e:
            logger.error(f"Failed to start jammer device: {e}")
            raise
    
    def stop(self):
        """Stop the jammer and close the device."""
        self.stop_jamming()
        if self.device:
            self.device.close()
            self.device = None
        logger.info("Jammer device stopped")
    
    def start_jamming(self, freq, bandwidth=None):
        """Start jamming at the specified frequency."""
        if self.jamming:
            self.stop_jamming()
        
        self.current_freq = freq
        self.current_bandwidth = bandwidth or 1.0  # Default 1 MHz bandwidth
        
        try:
            # Set center frequency in Hz
            self.device.center_freq = int(freq * 1e6)
            
            # Start jamming thread
            self.jamming = True
            self.jam_thread = threading.Thread(target=self._jam_loop)
            self.jam_thread.daemon = True
            self.jam_thread.start()
            
            logger.info(f"Started jamming at {freq} MHz with {self.current_bandwidth} MHz bandwidth")
            return True
        except Exception as e:
            logger.error(f"Failed to start jamming at {freq} MHz: {e}")
            self.jamming = False
            return False
    
    def stop_jamming(self):
        """Stop the current jamming operation."""
        if not self.jamming:
            return
        
        self.jamming = False
        if self.jam_thread:
            self.jam_thread.join(timeout=1.0)
            self.jam_thread = None
        
        logger.info(f"Stopped jamming at {self.current_freq} MHz")
        self.current_freq = None
        self.current_bandwidth = None
    
    def _jam_loop(self):
        """Main jamming loop that generates and transmits jamming signals."""
        try:
            # Generate jamming signal based on bandwidth
            if self.current_bandwidth < 0.5:
                # Narrowband jamming - use tone
                self._transmit_tone_jamming()
            else:
                # Wideband jamming - use noise
                self._transmit_noise_jamming()
        except Exception as e:
            logger.error(f"Error in jam loop: {e}")
            self.jamming = False
    
    def _transmit_tone_jamming(self):
        """Transmit a tone jamming signal."""
        # Generate a complex sine wave
        t = np.arange(0, 0.01, 1/self.sample_rate)  # 10ms of samples
        tone = self.amplitude * np.exp(2j * np.pi * 1000 * t)  # 1kHz offset tone
        samples = tone.astype(np.complex64)
        
        # Transmit continuously
        while self.jamming:
            try:
                self.device.tx(samples)
            except Exception as e:
                logger.error(f"Error transmitting tone: {e}")
                break
    
    def _transmit_noise_jamming(self):
        """Transmit a noise jamming signal."""
        # Generate complex white noise
        num_samples = int(0.01 * self.sample_rate)  # 10ms of samples
        
        while self.jamming:
            try:
                # Generate new noise for each transmission for better jamming
                i_samples = np.random.normal(0, 1, num_samples)
                q_samples = np.random.normal(0, 1, num_samples)
                noise = self.amplitude * (i_samples + 1j * q_samples)
                samples = noise.astype(np.complex64)
                
                self.device.tx(samples)
            except Exception as e:
                logger.error(f"Error transmitting noise: {e}")
                break
    
    def is_jamming(self):
        """Check if the jammer is currently active."""
        return self.jamming
    
    def get_current_frequency(self):
        """Get the frequency currently being jammed."""
        return self.current_freq

    def start_wideband_jamming(self, start_freq, end_freq):
        """Start jamming a wide band by sweeping noise."""
        if self.jamming:
            self.stop_jamming()

        self.current_freq = f"{start_freq}-{end_freq}"  # Store the range
        self.jamming = True
        
        self.jam_thread = threading.Thread(
            target=self._wideband_jam_loop,
            args=(start_freq, end_freq)
        )
        self.jam_thread.daemon = True
        self.jam_thread.start()
        
        logger.info(f"Started wideband jamming from {start_freq} to {end_freq} MHz")
        return True

    def _wideband_jam_loop(self, start_freq, end_freq):
        """Loop for wideband jamming sweep."""
        # Generate a short burst of noise samples
        num_samples = int(0.001 * self.sample_rate)
        i_samples = np.random.normal(0, 1, num_samples)
        q_samples = np.random.normal(0, 1, num_samples)
        noise = self.amplitude * (i_samples + 1j * q_samples)
        samples = noise.astype(np.complex64)

        # Step size is the sample rate bandwidth
        step_size_mhz = self.sample_rate / 1e6
        
        while self.jamming:
            try:
                # Sweep from start to end
                freq_mhz = start_freq
                while freq_mhz <= end_freq and self.jamming:
                    self.device.center_freq = int(freq_mhz * 1e6)
                    self.device.tx(samples)
                    freq_mhz += step_size_mhz
            except Exception as e:
                logger.error(f"Error in wideband jam loop: {e}")
                time.sleep(0.1)  # Wait a bit before restarting sweep

    def is_connected(self):
        """Check if the jammer device is connected."""
        return self.device is not None


if __name__ == "__main__":
    # Test the jammer
    jammer = Jammer()
    try:
        jammer.start()
        
        # Test jamming at 915 MHz
        test_freq = 915.0
        print(f"Starting jamming at {test_freq} MHz. Press Ctrl+C to stop.")
        jammer.start_jamming(test_freq)
        
        # Run for 10 seconds
        time.sleep(10)
        
        jammer.stop_jamming()
        print("Jamming stopped.")
        
    except KeyboardInterrupt:
        print("\nStopping jammer...")
    finally:
        jammer.stop()