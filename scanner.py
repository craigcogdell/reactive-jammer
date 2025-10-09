"""
Scanner module for the reactive jammer system.
Uses HackRF to scan for signals and stores them in a database.
"""

import time
import logging
import datetime
import numpy as np
from scipy.signal import welch, find_peaks
import hackrf
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from config import HACKRF_SETTINGS, SCANNER_SETTINGS, DATABASE_SETTINGS, GENERAL_SETTINGS

# Set up logging
logging.basicConfig(
    level=getattr(logging, GENERAL_SETTINGS['log_level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=GENERAL_SETTINGS['log_file']
)
logger = logging.getLogger('scanner')

Base = declarative_base()

class DetectedFrequency(Base):
    """Database model for detected frequencies."""
    __tablename__ = DATABASE_SETTINGS['table_name']
    
    id = Column(Integer, primary_key=True)
    center_freq = Column(Float, nullable=False, index=True)
    bandwidth = Column(Float, nullable=False)
    power = Column(Float, nullable=False)
    band_name = Column(String, nullable=False)
    first_seen = Column(DateTime, default=datetime.datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    detection_count = Column(Integer, default=1)
    hop_count = Column(Integer, default=0)

    def __repr__(self):
        return f"<DetectedFrequency(freq={self.center_freq:.3f} MHz, power={self.power:.1f} dBm)>"

class HopTransition(Base):
    """Database model for frequency hop transitions."""
    __tablename__ = 'hop_transitions'
    
    id = Column(Integer, primary_key=True)
    source_freq = Column(Float, nullable=False, index=True)
    dest_freq = Column(Float, nullable=False, index=True)
    count = Column(Integer, default=1)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<HopTransition({self.source_freq:.2f} -> {self.dest_freq:.2f}, count={self.count})>"

class Scanner:
    """HackRF scanner for detecting signals."""
    
    def __init__(self, device_index=0, simulation=False):
        """Initialize the scanner with the specified HackRF device."""
        self.device_index = device_index
        self.device = None
        self.simulation = simulation
        
        # Load settings from config
        self.sample_rate = HACKRF_SETTINGS['scanner']['sample_rate']
        self.if_gain = HACKRF_SETTINGS['scanner']['if_gain']
        self.bb_gain = HACKRF_SETTINGS['scanner']['bb_gain']
        self.fft_size = SCANNER_SETTINGS['fft_size']
        self.integration_time = SCANNER_SETTINGS['integration_time']
        self.threshold = SCANNER_SETTINGS['threshold']
        
        # Database connection
        self.engine = create_engine(f"sqlite:///{DATABASE_SETTINGS['db_file']}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
        logger.info("Scanner initialized")

    def start(self):
        """Start the scanner device."""
        if self.simulation:
            from fake_hackrf import FakeHackRF
            self.device = FakeHackRF()
            logger.info("Scanner started in simulation mode.")
            return True

        try:
            self.device = hackrf.HackRF(device_index=self.device_index)
            self.device.sample_rate = self.sample_rate
            self.device.lna_gain = self.if_gain
            self.device.vga_gain = self.bb_gain
            logger.info(f"Scanner device started on index {self.device_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to start scanner device: {e}")
            self.device = None
            return False

    def stop(self):
        """Stop the scanner and close the device."""
        if self.device:
            self.device.close()
            self.device = None
        logger.info("Scanner device stopped")

    def _scan_at_frequency(self, center_freq, band_name):
        """Scan at a specific center frequency and return the strongest detected signal."""
        if not self.device:
            logger.warning("Scanner device not started")
            return None
        
        try:
            self.device.center_freq = int(center_freq * 1e6)
            
            num_samples = int(self.sample_rate * self.integration_time)
            if num_samples < self.fft_size:
                num_samples = self.fft_size
            
            samples = self.device.read_samples(num_samples)
            
            freqs, psd = welch(
                samples,
                fs=self.sample_rate,
                nperseg=self.fft_size,
                return_onesided=False,
                scaling='density'
            )
            
            psd_db = 10 * np.log10(psd)
            psd_db = np.fft.fftshift(psd_db)
            freqs = np.fft.fftshift(freqs)
            
            peaks, properties = find_peaks(psd_db, height=self.threshold)
            
            if len(peaks) == 0:
                return None
            
            strongest_peak_idx = peaks[np.argmax(properties['peak_heights'])]
            power = properties['peak_heights'].max()
            
            signal_freq_offset = freqs[strongest_peak_idx]
            signal_freq = (center_freq * 1e6 + signal_freq_offset) / 1e6
            
            try:
                threshold_bw = power - 6
                left_idx = strongest_peak_idx
                while left_idx > 0 and psd_db[left_idx] > threshold_bw:
                    left_idx -= 1
                
                right_idx = strongest_peak_idx
                while right_idx < len(psd_db) - 1 and psd_db[right_idx] > threshold_bw:
                    right_idx += 1
                
                bandwidth_hz = freqs[right_idx] - freqs[left_idx]
                bandwidth = abs(bandwidth_hz) / 1e6
            except Exception:
                bandwidth = SCANNER_SETTINGS.get('min_signal_bw', 0.1)

            if bandwidth == 0:
                bandwidth = SCANNER_SETTINGS.get('min_signal_bw', 0.1)

            if not (SCANNER_SETTINGS['min_signal_bw'] <= bandwidth <= SCANNER_SETTINGS['max_signal_bw']):
                return None

            logger.info(f"Signal detected at {signal_freq:.3f} MHz, Power: {power:.1f} dB, BW: {bandwidth:.3f} MHz")
            
            signal_info = {
                'center_freq': signal_freq,
                'bandwidth': bandwidth,
                'power': power,
                'band_name': band_name,
                'timestamp': datetime.datetime.utcnow()
            }
            
            self._store_detection(signal_info)
            return signal_info
            
        except Exception as e:
            logger.error(f"Error scanning at {center_freq} MHz: {e}")
            return None

    def _store_detection(self, signal_info):
        """Store a detected frequency in the database."""
        session = self.Session()
        try:
            existing = session.query(DetectedFrequency).filter(
                DetectedFrequency.center_freq.between(
                    signal_info['center_freq'] - 0.1,
                    signal_info['center_freq'] + 0.1
                )
            ).first()
            
            if existing:
                existing.last_seen = signal_info['timestamp']
                existing.power = signal_info['power']
                existing.detection_count += 1
            else:
                new_freq = DetectedFrequency(
                    center_freq=signal_info['center_freq'],
                    bandwidth=signal_info['bandwidth'],
                    power=signal_info['power'],
                    band_name=signal_info['band_name']
                )
                session.add(new_freq)
            
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error storing detection: {e}")
        finally:
            session.close()

    def get_detected_frequencies(self, limit=10):
        """Get the most recently detected frequencies."""
        session = self.Session()
        try:
            return session.query(DetectedFrequency).order_by(
                DetectedFrequency.last_seen.desc()
            ).limit(limit).all()
        finally:
            session.close()

    def get_hopping_frequencies(self, limit=5):
        """Get frequencies suspected of hopping."""
        session = self.Session()
        try:
            return session.query(DetectedFrequency).filter(
                DetectedFrequency.hop_count > 2
            ).order_by(DetectedFrequency.last_seen.desc()).limit(limit).all()
        finally:
            session.close()

    def is_connected(self):
        """Check if the scanner device is connected."""
        return self.device is not None

if __name__ == '__main__':
    # Test the scanner
    scanner = Scanner()
    try:
        if scanner.start():
            print("Scanner started. Scanning 915 MHz for 10 seconds...")
            
            for _ in range(10):
                signal = scanner._scan_at_frequency(915.0, "ISM_915")
                if signal:
                    print(f"  Detected: {signal}")
                time.sleep(1)
            
            print("\nRecent detections:")
            recent = scanner.get_detected_frequencies()
            for freq in recent:
                print(f"  - {freq}")
                
    except KeyboardInterrupt:
        print("\nStopping scanner...")
    finally:
        scanner.stop()