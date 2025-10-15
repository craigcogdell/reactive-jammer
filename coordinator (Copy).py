"""
Coordinator module for the reactive jammer system.
Manages communication between scanner and jammer modules.
"""

import time
import logging
import threading
import datetime
import queue
from collections import deque
from scanner import Scanner, DetectedFrequency, HopTransition
from jammer import Jammer
from config import GENERAL_SETTINGS, DATABASE_SETTINGS, TARGET_FREQUENCIES
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Simulation-specific imports
from simulation import SimulationState, SignalGenerator

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
    
    def __init__(self, scanner_device_index=0, jammer_device_index=1, attack_mode='targeted', simulation=False, jam=False):
        """Initialize the coordinator with scanner and jammer devices."""
        self.simulation = simulation
        self.sim_state = None
        self.sim_thread = None
        self.sim_running_flag = None

        # Initialize scanner and jammer
        if self.simulation:
            self.sim_state = SimulationState()
            self.sim_running_flag = threading.Event()
            self.scanner = Scanner(device_index=scanner_device_index, simulation=simulation, simulation_state=self.sim_state)
            self.jammer = Jammer(device_index=jammer_device_index, simulation=simulation, simulation_state=self.sim_state)
        else:
            self.scanner = Scanner(device_index=scanner_device_index, simulation=simulation)
            self.jammer = Jammer(device_index=jammer_device_index, simulation=simulation)
        
        self.jam_enabled = jam
        
        # Database connection
        self.engine = create_engine(f"sqlite:///{DATABASE_SETTINGS['db_file']}")
        self.Session = sessionmaker(bind=self.engine)
        
        # Coordination state
        self.running = False
        self.coord_thread = None
        self.db_writer_thread = None
        self.current_target = None
        self.hopping_mode = False
        self.last_scan_time = 0
        self.scan_mode = GENERAL_SETTINGS['scan_mode']
        self.attack_mode = attack_mode
        self.active_scan_bands = list(GENERAL_SETTINGS.get('priority_frequencies', []))
        self.hop_history = deque(maxlen=10)
        self.mode_lock = threading.Lock() # Lock for safely changing modes
        
        logger.info(f"Coordinator initialized in '{self.attack_mode}' attack mode")
        
        # Database connection
        self.engine = create_engine(f"sqlite:///{DATABASE_SETTINGS['db_file']}")
        self.Session = sessionmaker(bind=self.engine)
        
        # Coordination state
        self.running = False
        self.coord_thread = None
        self.db_writer_thread = None
        self.current_target = None
        self.hopping_mode = False
        self.last_scan_time = 0
        self.scan_mode = GENERAL_SETTINGS['scan_mode']
        self.attack_mode = attack_mode
        self.hop_history = deque(maxlen=10)
        self.mode_lock = threading.Lock() # Lock for safely changing modes
        
        logger.info(f"Coordinator initialized in '{self.attack_mode}' attack mode")

    def set_attack_mode(self, mode):
        """Safely change the attack mode."""
        if mode not in ['targeted', 'wide_band']:
            logger.warning(f"Invalid attack mode: {mode}")
            return

        with self.mode_lock:
            if self.attack_mode == mode:
                return
            
            logger.info(f"Changing attack mode from '{self.attack_mode}' to '{mode}'")
            self.attack_mode = mode

            # Stop current activities
            if self.jammer.is_jamming():
                self.jammer.stop_jamming()
            
            self.hopping_mode = False
            self.current_target = None

            # Adjust components for the new mode
            if mode == 'wide_band':
                if self.scanner.is_connected():
                    logger.info("Stopping scanner for wide_band mode.")
                    self.scanner.stop()
            else: # targeted mode
                if not self.scanner.is_connected():
                    logger.info("Starting scanner for targeted mode.")
                    self.scanner.start()

    def set_scan_mode(self, mode):
        """Change the scan mode."""
        if mode not in ['priority_first', 'sequential', 'random']:
            logger.warning(f"Invalid scan mode: {mode}")
            return
        
        logger.info(f"Changing scan mode to '{mode}'")
        self.scan_mode = mode

    def set_scan_bands(self, bands):
        """Set the list of bands to be scanned in targeted mode."""
        logger.info(f"Updating scan bands to: {bands}")
        self.active_scan_bands = bands

    def get_available_bands(self):
        """Returns a list of all configured bands and whether they are priority."""
        all_bands = []
        for band_name in TARGET_FREQUENCIES.keys():
            all_bands.append({
                "name": band_name,
                "is_priority": band_name in self.active_scan_bands
            })
        return {"bands": all_bands}

    def start_wideband_jamming_by_name(self, band_name):
        """Initiates a wide-band attack on a specific, named band."""
        if band_name not in TARGET_FREQUENCIES:
            logger.error(f"Cannot start wide-band attack: Unknown band name '{band_name}'")
            return

        logger.info(f"Received command to start wide-band attack on {band_name}")
        self.set_attack_mode('wide_band')

        # If in simulation, create a temporary signal in this band for visual feedback
        if self.simulation and self.sim_thread:
            self.sim_thread.generate_transient_signal(band_name)
        
        band_data = TARGET_FREQUENCIES[band_name]
        if isinstance(band_data, list):
            start_freq = band_data[0]['start']
            end_freq = band_data[-1]['end']
        else:
            start_freq = band_data['start']
            end_freq = band_data['end']

        logger.info(f"Starting wide band attack on {band_name} ({start_freq} - {end_freq} MHz)")
        self.jammer.start_wideband_jamming(start_freq, end_freq)

    def set_manual_target(self, freq, bandwidth):
        """Overrides automated targeting to jam a specific frequency."""
        logger.info(f"Manual target override: {freq} MHz")
        # Create a temporary object that mimics the DetectedFrequency db object
        manual_target = type('ManualTarget', (object,), {
            'center_freq': freq,
            'bandwidth': bandwidth or 1.0,
            'power': -10, # Assign arbitrary high power
            'band_name': 'MANUAL',
            'hop_count': 0
        })()
        self._start_jamming_target(manual_target)


    
    def start(self):
        """Start the coordinator, scanner, and jammer."""
        if self.running:
            logger.warning("Coordinator already running")
            return
        
        try:
            # In wide_band mode, we only need the jammer
            if self.attack_mode != 'wide_band':
                self.scanner.start()

            if self.jam_enabled:
                self.jammer.start()
            else:
                logger.warning("Jammer is disabled. Run with --jam to enable it.")
            
            # Start coordination thread
            self.running = True
            self.coord_thread = threading.Thread(target=self._coordination_loop)
            self.coord_thread.daemon = True
            self.coord_thread.start()

            if self.simulation:
                self.sim_running_flag.set()
                self.sim_thread = SignalGenerator(self.sim_state, self.sim_running_flag)
                self.sim_thread.start()
                logger.info("SignalGenerator thread started for simulation")
            
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

        if self.simulation and self.sim_thread:
            self.sim_running_flag.clear()
            self.sim_thread.join(timeout=1.0)
            logger.info("SignalGenerator thread stopped")
        
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

    def _calculate_threat_score(self, signal):
        """Calculate a threat score for a given signal."""
        score = 0
        # Power-based score (normalized)
        score += max(0, (signal.power + 100) / 10) # Scale power from -100-0 dBm to 0-10 points

        # Priority band bonus
        if signal.band_name in GENERAL_SETTINGS.get('priority_frequencies', []):
            score += 20

        # Hopping bonus (significant bonus for hopping)
        if signal.hop_count > 1:
            score += 30 * signal.hop_count
        
        return score

    
    def _handle_normal_scanning(self):
        """Handle normal scanning mode by prioritizing highest threat scores."""
        session = self.Session()
        try:
            # 1. Prioritize the highest threat score from the database
            highest_threat = session.query(DetectedFrequency).order_by(
                DetectedFrequency.threat_score.desc()
            ).first()

            if highest_threat:
                # Check if we are already jamming this target
                if not (self.current_target and abs(self.current_target.center_freq - highest_threat.center_freq) < 0.1):
                    # Check if the high-threat signal is currently active
                    signal = self.scanner._scan_at_frequency(highest_threat.center_freq, highest_threat.band_name)
                    if signal:
                        logger.info(f"High-threat signal re-acquired: {highest_threat.center_freq} MHz with score {highest_threat.threat_score}")
                        # Update the database with the new detection info before jamming
                        highest_threat.last_seen = datetime.datetime.utcnow()
                        highest_threat.power = signal['power']
                        highest_threat.threat_score = self._calculate_threat_score(highest_threat)
                        session.commit()
                        self._start_jamming_target(highest_threat)
                        return # Exit after finding and jamming the highest threat

            # 2. If no high-threat target is active, proceed with normal scanning
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
        for band_name in self.active_scan_bands:
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
        """Scans a frequency range thoroughly and jams the first detected signal."""
        if not self.scanner.is_connected():
            logger.warning("Scanner not connected, cannot scan range.")
            time.sleep(1.0)
            return

        scan_step_mhz = self.scanner.sample_rate / 1e6
        current_freq = start_freq

        logger.debug(f"Sweeping band {band_name} from {start_freq} to {end_freq} MHz.")
        while current_freq < end_freq:
            if not self.running or self.attack_mode != 'targeted':
                logger.info("Stopping scan due to mode change or shutdown.")
                break

            signal = self.scanner._scan_at_frequency(current_freq, band_name)
            if signal:
                detection_time = time.time()
                logger.info(f"Signal detected at {signal['center_freq']} MHz.")
                
                # Save the detection and get the DB object
                detected_obj = self._save_detection_to_db(signal)
                
                # Jam the newly found target
                if detected_obj:
                    self._start_jamming_target(detected_obj, detection_time)
                return # Stop scanning this band and let main loop re-evaluate threats

            current_freq += scan_step_mhz

    def _save_detection_to_db(self, signal_info):
        """Stores a new detection in the database and updates its threat score."""
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
                # Recalculate score on new detection
                existing.threat_score = self._calculate_threat_score(existing)
                session.commit()
                return existing
            else:
                new_freq = DetectedFrequency(
                    center_freq=signal_info['center_freq'],
                    bandwidth=signal_info['bandwidth'],
                    power=signal_info['power'],
                    band_name=signal_info['band_name']
                )
                # Calculate initial score
                new_freq.threat_score = self._calculate_threat_score(new_freq)
                session.add(new_freq)
                session.commit()
                return new_freq
        except Exception as e:
            session.rollback()
            logger.error(f"Database error storing detection: {e}")
            return None
        finally:
            session.close()
    
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
        """Predicts the next hop based on linear progression and historical data."""
        # 1. Try to detect a linear hop sequence from history
        if len(self.hop_history) >= 2:
            last_hop = self.hop_history[-1]
            second_last_hop = self.hop_history[-2]

            # Check if the sequence is contiguous: A->B, then B->C
            if abs(last_hop[0] - second_last_hop[1]) < 0.1: # Allow for small freq inaccuracies
                hop_delta1 = last_hop[1] - last_hop[0]
                hop_delta2 = second_last_hop[1] - second_last_hop[0]

                # If deltas are similar, predict the next hop
                if abs(hop_delta1 - hop_delta2) < 0.2:  # Tolerance for small variations
                    predicted_freq = last_hop[1] + hop_delta1
                    logger.info(f"Predicted next hop based on linear progression: {predicted_freq:.2f} MHz")
                    return predicted_freq

        # 2. If no linear progression, fall back to database lookup
        session = self.Session()
        try:
            # Round frequency to match stored data
            current_freq_rounded = round(current_freq, 2)
            
            most_likely_hop = session.query(HopTransition).filter_by(
                source_freq=current_freq_rounded
            ).order_by(HopTransition.count.desc()).first()

            if most_likely_hop:
                logger.info(f"Predicted next hop from DB: {most_likely_hop.dest_freq} MHz")
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
                self.hop_history.append((current_freq, signal['center_freq']))
                self._record_hop_transition(current_freq, signal['center_freq'])
                self._update_and_jam_new_freq(signal, band_name)
                return
            else:
                logger.info(f"Hop prediction failed. No signal at predicted frequency {predicted_freq} MHz.")

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
            self.hop_history.append((current_freq, strongest_signal['center_freq']))
            self._record_hop_transition(current_freq, strongest_signal['center_freq'])
            self._update_and_jam_new_freq(strongest_signal, band_name)
        elif not strongest_signal:
            logger.info("No signal found in hopping range, transmission may have stopped.")
            self.jammer.stop_jamming()
            self.hopping_mode = False
            self.current_target = None
    
    def _start_jamming_target(self, target, detection_time=None):
        """Start jamming a detected frequency."""
        if self.jammer.is_jamming():
            self.jammer.stop_jamming()
        
        logger.info(f"Starting to jam {target.center_freq} MHz")
        
        # Start jamming
        success = self.jammer.start_jamming(target.center_freq, target.bandwidth)
        
        if success:
            if detection_time:
                jam_time = time.time()
                latency = (jam_time - detection_time) * 1000  # in milliseconds
                logger.info(f"Jamming started at {jam_time}. Reaction time: {latency:.2f} ms")
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

    def get_spectrum_data(self):
        """Get spectrum data from the scanner."""
        if self.scanner:
            return self.scanner.get_last_scan_data()
        return None

    def start_jamming(self, freq, bandwidth=None, power=None):
        """Manually start jamming a frequency."""
        if self.jammer:
            # The jammer's start_jamming method might need to be adapted
            # if it doesn't accept power, or we can just ignore it.
            self.jammer.start_jamming(freq, bandwidth)
            logger.info(f"Manual jamming started at {freq} MHz")

    def stop_jamming(self):
        """Manually stop jamming."""
        if self.jammer:
            self.jammer.stop_jamming()
            logger.info("Manual jamming stopped")

    def reload_config(self):
        """Reload configuration from file."""
        global GENERAL_SETTINGS, HACKRF_SETTINGS, SCANNER_SETTINGS, DATABASE_SETTINGS, TARGET_FREQUENCIES
        try:
            import importlib
            from config import GENERAL_SETTINGS, HACKRF_SETTINGS, SCANNER_SETTINGS, DATABASE_SETTINGS, TARGET_FREQUENCIES
            importlib.reload(config)
            
            # Update coordinator attributes
            self.scan_mode = GENERAL_SETTINGS['scan_mode']
            self.attack_mode = GENERAL_SETTINGS['attack_mode']
            
            # Update scanner and jammer settings if they are running
            if self.scanner and self.scanner.device:
                self.scanner.apply_settings(HACKRF_SETTINGS['scanner'], SCANNER_SETTINGS)
            if self.jammer and self.jammer.device:
                self.jammer.apply_settings(HACKRF_SETTINGS['jammer'])

            logger.info("Configuration reloaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            return False


# Import here to avoid circular imports
from config import TARGET_FREQUENCIES
import config

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