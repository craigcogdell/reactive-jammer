#!/usr/bin/env python3
"""
Reactive Jammer - Main Program

This program orchestrates the reactive jammer system using two HackRF devices:
- One HackRF for scanning frequencies
- One HackRF for jamming detected signals

The system can detect and jam signals on:
- 433MHz ISM Band
- 868MHz ISM Band
- 915MHz ISM Band
- 2.4GHz WiFi Band
- 5GHz WiFi Band
- Various cellular frequency bands

It can also detect frequency hopping and adapt jamming accordingly.
"""

import os
import sys
import time
import argparse
import logging
import signal
import threading
from coordinator import Coordinator
from web_ui import run_web_server
from config import GENERAL_SETTINGS, TARGET_FREQUENCIES

# Set up logging
logging.basicConfig(
    level=getattr(logging, GENERAL_SETTINGS['log_level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=GENERAL_SETTINGS['log_file'],
    filemode='a'
)

# Add console handler
console = logging.StreamHandler()
console.setLevel(getattr(logging, GENERAL_SETTINGS['log_level']))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

logger = logging.getLogger('main')

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Reactive Jammer - Detect and jam signals with frequency hopping detection'
    )
    
    parser.add_argument(
        '--scanner-index', 
        type=int, 
        default=0,
        help='HackRF device index for scanner (default: 0)'
    )
    
    parser.add_argument(
        '--jammer-index', 
        type=int, 
        default=1,
        help='HackRF device index for jammer (default: 1)'
    )
    
    parser.add_argument(
        '--scan-mode',
        choices=['priority_first', 'sequential', 'random'],
        default=GENERAL_SETTINGS['scan_mode'],
        help='Scanning mode (default: priority_first)'
    )
    
    parser.add_argument(
        '--attack-mode',
        choices=['targeted', 'wide_band'],
        default=GENERAL_SETTINGS['attack_mode'],
        help='Attack mode (default: targeted)'
    )

    parser.add_argument(
        '--simulate',
        action='store_true',
        help='Run in simulation mode without real hardware'
    )
    
    parser.add_argument(
        '--bands',
        nargs='+',
        choices=list(TARGET_FREQUENCIES.keys()),
        help='Specific bands to scan and jam (default: all bands)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default=GENERAL_SETTINGS['log_level'],
        help='Logging level (default: INFO)'
    )
    
    return parser.parse_args()

def print_banner():
    """Print the program banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║               REACTIVE JAMMER SYSTEM                      ║
    ║                                                           ║
    ║  Scan - Detect - Jam - Adapt                             ║
    ║                                                           ║
    ║  Target Frequencies:                                      ║
    ║    - 433MHz ISM Band                                      ║
    ║    - 868MHz ISM Band                                      ║
    ║    - 915MHz ISM Band                                      ║
    ║    - 2.4GHz WiFi Band                                     ║
    ║    - 5GHz WiFi Band                                       ║
    ║    - Cellular Bands                                       ║
    ║                                                           ║
    ║  Features:                                                ║
    ║    - Frequency hopping detection                          ║
    ║    - Historical frequency database                        ║
    ║    - Adaptive jamming                                     ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)

def print_status(coordinator):
    """Print the current status of the system."""
    status = coordinator.get_status()
    
    print("\n--- SYSTEM STATUS ---")
    print(f"Running: {status['running']}")
    print(f"Scan Mode: {status['scan_mode']}")
    print(f"Hopping Detection: {'ACTIVE' if status['hopping_mode'] else 'INACTIVE'}")
    
    if status['current_target']:
        print("\n--- CURRENT TARGET ---")
        print(f"Frequency: {status['current_target']['frequency']:.3f} MHz")
        print(f"Bandwidth: {status['current_target']['bandwidth']:.2f} MHz")
        print(f"Power: {status['current_target']['power']:.1f} dBm")
        print(f"Band: {status['current_target']['band']}")
        print(f"Jamming: {'ACTIVE' if status['jamming'] else 'INACTIVE'}")
    else:
        print("\nNo current jamming target. Scanning...")
    
    # Get recent frequencies
    recent_freqs = coordinator.scanner.get_detected_frequencies(5)
    if recent_freqs:
        print("\n--- RECENTLY DETECTED FREQUENCIES ---")
        for freq in recent_freqs:
            print(f"  {freq.center_freq:.3f} MHz, Power: {freq.power:.1f} dBm, Band: {freq.band_name}")
    
    # Get hopping frequencies
    hopping_freqs = coordinator.scanner.get_hopping_frequencies(3)
    if hopping_freqs:
        print("\n--- FREQUENCY HOPPING SIGNALS ---")
        for freq in hopping_freqs:
            print(f"  {freq.center_freq:.3f} MHz, Hop Count: {freq.hop_count}, Band: {freq.band_name}")
    
    print("\nPress Ctrl+C to exit")

def main():
    """Main function."""
    args = parse_arguments()
    
    # Set log level
    logging.getLogger('').setLevel(getattr(logging, args.log_level))
    
    print_banner()
    
    # Create coordinator
    coordinator = Coordinator(
        scanner_device_index=args.scanner_index,
        jammer_device_index=args.jammer_index,
        attack_mode=args.attack_mode,
        simulation=args.simulate
    )
    
    # Set scan mode if specified
    if args.scan_mode:
        coordinator.scan_mode = args.scan_mode
    
    # Handle signals for graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutting down reactive jammer...")
        coordinator.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start the coordinator
        if not coordinator.start():
            logger.error("Failed to start coordinator")
            return 1
        
        logger.info("Reactive jammer system started")

        # Start the web server in a background thread
        web_thread = threading.Thread(
            target=run_web_server,
            args=(coordinator,),
            daemon=True
        )
        web_thread.start()
        
        # Main loop now just keeps the program alive
        while True:
            print_status(coordinator)
            time.sleep(5)  # Update status every 5 seconds
            
            # Clear screen for next update
            os.system('cls' if os.name == 'nt' else 'clear')
            
    except KeyboardInterrupt:
        print("\nShutting down reactive jammer...")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        coordinator.stop()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())