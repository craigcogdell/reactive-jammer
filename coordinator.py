"""
Coordinator module for the reactive jammer system.
Manages communication between scanner and jammer modules.
"""

import time
import logging
import threading
import datetime
from scanner import Scanner, DetectedFrequency, HopTransition
from jammer import Jammer
from config import GENERAL_SETTINGS, DATABASE_SETTINGS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Set up logging
logging.basicConfig(
    level=getattr(logging, GENERAL_SETTINGS['log_level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=GENERAL_SETTINGS['log_file']
)
logger = logging.getLogger('coordinator')

Base = declarative_base()

class Coordinator:
    """Coordinates the scanner and jammer modules."""
    
    def __init__(self, scanner_device_index=0, jammer_device_index=1, attack_mode='targeted', simulation=False):
        """Initialize the coordinator with scanner and jammer devices."""
        self.scanner = Scanner(device_index=scanner_device_index, simulation=simulation)
        self.jammer = Jammer(device_index=jammer_device_index, simulation=simulation)
        
        # Database connection
        self.engine = create_engine(f"sqlite:///{DATABASE_SETTINGS['db_file']}")
        self.Session = sessionmaker(bind=self.engine)
        
        # Coordination state
        self.running = False
        self.coord_thread = None
        self.current_target = None
        self.hopping_mode = False
        self.last_scan_time = 0
        self.scan_mode = GENERAL_SETTINGS['scan_mode']
        self.attack_mode = attack_mode
        
        logger.info(f"Coordinator initialized in '{self.attack_mode}' attack mode")
    
    def start(self):
        """Start the coordinator, scanner, and jammer."""
        if self.running:
            logger.warning("Coordinator already running")
            return
        
        try:
            # In wide_band mode, we only need the jammer
            if self.attack_mode != 'wide_band':
                self.scanner.start()

            self.jammer.start()
            
            # Start coordination thread
            self.running = True
            self.coord_thread = threading.Thread(target=self._coordination_loop)
            self.coord_thread.daemon = True
            self.coord_thread.start()
            
            logger.info("Coordinator started")
            return True
        except Exception as e:
            logger.error(f"Failed to start coordinator: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop the coordinator, scanner, and jammer."""
        self.running = False
        
        if self.coord_thread:
            self.coord_thread.join(timeout=2.0)
        
        # Stop jammer and scanner
        if hasattr(self, 'jammer') and self.jammer:
            self.jammer.stop()
        
        if hasattr(self, 'scanner') and self.scanner:
            self.scanner.stop()
        
        logger.info("Coordinator stopped")
    
    def _coordination_loop(self):
        """Main coordination loop."""
        while self.running:
            try:
                if self.attack_mode == 'wide_band':
                    self._handle_wide_band_attack()
                elif self.hopping_mode:
                    self._handle_frequency_hopping()
                else:
                    self._handle_normal_scanning()
                
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in coordination loop: {e}")
                time.sleep(1.0)

    def _handle_wide_band_attack(self):
        """Handles the wide band attack mode."""
        # This mode jams the first priority band from the config.
        if not self.jammer.is_jamming():
            try:
                band_name_to_jam = GENERAL_SETTINGS['priority_frequencies'][0]
                band_data = TARGET_FREQUENCIES[band_name_to_jam]
                
                if isinstance(band_data, list):
                    start_freq = band_data[0]['start']
                    end_freq = band_data[-1]['end']
                else:
                    start_freq = band_data['start']
                    end_freq = band_data['end']

                logger.info(f"Starting wide band attack on {band_name_to_jam} ({start_freq} - {end_freq} MHz)")
                self.jammer.start_wideband_jamming(start_freq, end_freq)
            except Exception as e:
                logger.error(f"Could not start wide band attack: {e}")
                self.running = False
        
        # Keep thread alive; jammer is doing the work in its own thread.
        time.sleep(5)
    
    def _handle_normal_scanning(self):
        """Handle normal scanning mode."""
        # First check previously detected frequencies
        session = self.Session()
        try:
            # Get historical frequencies ordered by most recently seen
            historical_freqs = session.query(DetectedFrequency).order_by(
                DetectedFrequency.last_seen.desc()
            ).limit(DATABASE_SETTINGS['history_limit']).all()
            
            # Check if any historical frequencies are active
            for freq in historical_freqs:
                # Skip if we're already jamming this frequency
                if (self.current_target and 
                    abs(self.current_target.center_freq - freq.center_freq) < 0.1):
                    continue
                
                # Scan this specific frequency to see if it's active
                signal = self.scanner._scan_at_frequency(freq.center_freq, freq.band_name)
                if signal:
                    logger.info(f"Historical frequency active: {freq.center_freq} MHz")
                    self._start_jamming_target(freq)
                    return
            
            # If no historical frequencies are active, perform wide scanning
            # based on the configured scan mode
            if self.scan_mode == 'priority_first':
                self._scan_priority_bands()
            elif self.scan_mode == 'sequential':
                self._scan_sequential()
            else:  # random mode
                self._scan_random()
                
        except Exception as e:
            logger.error(f"Error in normal scanning: {e}")
        finally:
            session.close()
    
    def _scan_priority_bands(self):
        """Scan priority frequency bands first."""
        for band_name in GENERAL_SETTINGS['priority_frequencies']:
            if band_name in TARGET_FREQUENCIES:
                band_data = TARGET_FREQUENCIES[band_name]
                if isinstance(band_data, list):
                    for range_data in band_data:
                        self._scan_and_jam_range(range_data['start'], range_data['end'], band_name)
                else:
                    self._scan_and_jam_range(band_data['start'], band_data['end'], band_name)
    
    def _scan_sequential(self):
        """Scan all frequency bands sequentially."""
        for band_name, band_data in TARGET_FREQUENCIES.items():
            if isinstance(band_data, list):
                for range_data in band_data:
                    self._scan_and_jam_range(range_data['start'], range_data['end'], band_name)
            else:
                self._scan_and_jam_range(band_data['start'], band_data['end'], band_name)
    
    def _scan_random(self):
        """Scan a random frequency band."""
        import random
        band_names = list(TARGET_FREQUENCIES.keys())
        band_name = random.choice(band_names)
        
        band_data = TARGET_FREQUENCIES[band_name]
        if isinstance(band_data, list):
            range_data = random.choice(band_data)
            self._scan_and_jam_range(range_data['start'], range_data['end'], band_name)
        else:
            self._scan_and_jam_range(band_data['start'], band_data['end'], band_name)
    
    def _scan_and_jam_range(self, start_freq, end_freq, band_name):
        """Scan a frequency range and jam any detected signals."""
        # Calculate a few points to scan within the range
        points = 5  # Number of points to check
        step = (end_freq - start_freq) / points
        
        for i in range(points):
            freq = start_freq + i * step
            signal = self.scanner._scan_at_frequency(freq, band_name)
            
            if signal:
                # Create a DetectedFrequency object for this signal
                detected = DetectedFrequency(
                    center_freq=signal['center_freq'],
                    bandwidth=signal['bandwidth'],
                    power=signal['power'],
                    band_name=band_name
                )
                self._start_jamming_target(detected)
                return
    
    def _record_hop_transition(self, source_freq, dest_freq):
        """Records a hop transition in the database."""
        session = self.Session()
        try:
            # Round frequencies to avoid minor precision issues
            source_freq = round(source_freq, 2)
            dest_freq = round(dest_freq, 2)

            transition = session.query(HopTransition).filter_by(
                source_freq=source_freq,
                dest_freq=dest_freq
            ).first()

            if transition:
                transition.count += 1
                transition.last_seen = datetime.datetime.utcnow()
            else:
                new_transition = HopTransition(
                    source_freq=source_freq,
                    dest_freq=dest_freq
                )
                session.add(new_transition)
            session.commit()
            logger.info(f"Recorded hop transition: {source_freq} -> {dest_freq}")
        except Exception as e:
            session.rollback()
            logger.error(f"Database error recording hop transition: {e}")
        finally:
            session.close()

    def _predict_next_hop(self, current_freq):
        """Predicts the next hop based on historical data."""
        session = self.Session()
        try:
            # Round frequency to match stored data
            current_freq = round(current_freq, 2)
            
            most_likely_hop = session.query(HopTransition).filter_by(
                source_freq=current_freq
            ).order_by(HopTransition.count.desc()).first()

            if most_likely_hop:
                logger.info(f"Predicted next hop from {current_freq} is {most_likely_hop.dest_freq} MHz")
                return most_likely_hop.dest_freq
            return None
        finally:
            session.close()

    def _update_and_jam_new_freq(self, signal_info, band_name):
        """Updates the database and retasks the jammer to a new frequency."""
        # Update current target
        self.current_target.center_freq = signal_info['center_freq']
        self.current_target.bandwidth = signal_info['bandwidth']
        self.current_target.power = signal_info['power']
        
        # Start jamming the new frequency
        self.jammer.stop_jamming()
        self.jammer.start_jamming(
            signal_info['center_freq'],
            signal_info['bandwidth']
        )
        
        # Update the database
        session = self.Session()
        try:
            existing = session.query(DetectedFrequency).filter(
                DetectedFrequency.center_freq.between(
                    signal_info['center_freq'] - 0.1,
                    signal_info['center_freq'] + 0.1
                )
            ).first()
            
            if existing:
                existing.hop_count += 1
                existing.last_seen = signal_info['timestamp']
                existing.power = signal_info['power']
            else:
                new_freq = DetectedFrequency(
                    center_freq=signal_info['center_freq'],
                    bandwidth=signal_info['bandwidth'],
                    power=signal_info['power'],
                    hop_count=1,
                    band_name=band_name
                )
                session.add(new_freq)
            
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error in _update_and_jam_new_freq: {e}")
        finally:
            session.close()

    def _handle_frequency_hopping(self):
        """Handle frequency hopping detection and jamming, with prediction."""
        if not self.jammer.is_jamming() or not self.current_target:
            logger.info("No active jamming target, exiting hopping mode.")
            self.hopping_mode = False
            self.current_target = None
            return

        current_freq = self.jammer.get_current_frequency()
        band_name = self.current_target.band_name
        
        # 1. Try to predict the next hop
        predicted_freq = self._predict_next_hop(current_freq)
        if predicted_freq:
            signal = self.scanner._scan_at_frequency(predicted_freq, band_name)
            if signal:
                logger.info(f"Hop prediction successful! New frequency: {signal['center_freq']:.3f} MHz")
                self._record_hop_transition(current_freq, signal['center_freq'])
                self._update_and_jam_new_freq(signal, band_name)
                return

        # 2. If prediction fails, fall back to sweeping
        logger.debug("Hop prediction failed or no prediction available, sweeping for signal.")
        scan_width = 10.0
        start_freq = current_freq - scan_width
        end_freq = current_freq + scan_width
        
        strongest_signal = None
        strongest_power = -float('inf')
        
        points = 10
        step = (end_freq - start_freq) / points
        
        for i in range(points):
            freq = start_freq + i * step
            signal = self.scanner._scan_at_frequency(freq, band_name)
            if signal and signal['power'] > strongest_power:
                strongest_signal = signal
                strongest_power = signal['power']
        
        if strongest_signal and abs(strongest_signal['center_freq'] - current_freq) > 0.5:
            logger.info(f"Frequency hop detected by sweep: {current_freq:.3f} -> {strongest_signal['center_freq']:.3f} MHz")
            self._record_hop_transition(current_freq, strongest_signal['center_freq'])
            self._update_and_jam_new_freq(strongest_signal, band_name)
        elif not strongest_signal:
            logger.info("No signal found in hopping range, transmission may have stopped.")
            self.jammer.stop_jamming()
            self.hopping_mode = False
            self.current_target = None
    
    def _start_jamming_target(self, target):
        """Start jamming a detected frequency."""
        if self.jammer.is_jamming():
            self.jammer.stop_jamming()
        
        logger.info(f"Starting to jam {target.center_freq} MHz")
        
        # Start jamming
        success = self.jammer.start_jamming(target.center_freq, target.bandwidth)
        
        if success:
            self.current_target = target
            
            # Check if this is a hopping frequency
            session = self.Session()
            try:
                existing = session.query(DetectedFrequency).filter(
                    DetectedFrequency.center_freq.between(
                        target.center_freq - 0.1,
                        target.center_freq + 0.1
                    )
                ).first()
                
                if existing and existing.hop_count >= 3:
                    logger.info(f"Entering hopping mode for {target.center_freq} MHz")
                    self.hopping_mode = True
                else:
                    self.hopping_mode = False
            except Exception as e:
                logger.error(f"Database error checking hop count: {e}")
            finally:
                session.close()
        else:
            logger.error(f"Failed to start jamming {target.center_freq} MHz")
            self.current_target = None
            self.hopping_mode = False
    
    def get_status(self):
        """Get the current status of the coordinator for the web UI."""
        status = {
            "running": self.running,
            "hopping_mode": self.hopping_mode,
            "scan_mode": self.scan_mode,
            "attack_mode": self.attack_mode,
            "scanner_connected": self.scanner.is_connected(),
            "jammer_connected": self.jammer.is_connected(),
            "jamming": False,
            "current_target": None,
            "recent_detections": []
        }

        if self.jammer and self.jammer.is_jamming() and self.current_target:
            status["jamming"] = True
            status["current_target"] = {
                "frequency": self.current_target.center_freq,
                "bandwidth": self.current_target.bandwidth,
                "power": self.current_target.power,
                "band": self.current_target.band_name
            }
        
        if self.scanner:
            recent_freqs = self.scanner.get_detected_frequencies(10)
            status["recent_detections"] = [
                {
                    "frequency": f.center_freq,
                    "power": f.power,
                    "band": f.band_name,
                    "last_seen": f.last_seen.isoformat()
                } for f in recent_freqs
            ]
            
        return status


# Import here to avoid circular imports
from config import TARGET_FREQUENCIES

if __name__ == "__main__":
    # Test the coordinator
    coordinator = Coordinator()
    try:
        coordinator.start()
        print("Coordinator running. Press Ctrl+C to stop.")
        
        while True:
            time.sleep(2)
            status = coordinator.get_status()
            print("\nCurrent status:")
            print(f"  Running: {status['running']}")
            print(f"  Hopping mode: {status['hopping_mode']}")
            print(f"  Scan mode: {status['scan_mode']}")
            
            if status['current_target']:
                print(f"  Target: {status['current_target']['frequency']} MHz "
                      f"({status['current_target']['band']})")
                print(f"  Jamming: {status['jamming']}")
            else:
                print("  No current target")
    
    except KeyboardInterrupt:
        print("\nStopping coordinator...")
    finally:
        coordinator.stop()