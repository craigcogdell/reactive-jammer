import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from scanner import Scanner, DetectedFrequency, HopTransition

class TestScanner(unittest.TestCase):

    @patch('scanner.hackrf')
    @patch('scanner.create_engine')
    def setUp(self, mock_create_engine, mock_hackrf):
        # Mock the database engine and session
        self.mock_engine = MagicMock()
        mock_create_engine.return_value = self.mock_engine
        self.mock_session = MagicMock()
        self.mock_engine.connect.return_value = self.mock_session

        # Mock the HackRF device
        self.mock_hackrf_device = MagicMock()
        mock_hackrf.HackRF.return_value = self.mock_hackrf_device

        self.scanner = Scanner(device_index=0)

    def test_start_stop(self):
        self.assertTrue(self.scanner.start())
        self.assertIsNotNone(self.scanner.device)
        self.scanner.stop()
        self.assertIsNone(self.scanner.device)

    def test_scan_at_frequency_no_signal(self):
        # Configure the mock device to return noise
        self.mock_hackrf_device.read_samples.return_value = self.generate_noise(1024)
        signal = self.scanner._scan_at_frequency(100.0, 'TEST')
        self.assertIsNone(signal)

    def test_scan_at_frequency_with_signal(self):
        # Configure the mock device to return a signal
        self.mock_hackrf_device.read_samples.return_value = self.generate_signal(100.0, 1024)
        signal = self.scanner._scan_at_frequency(100.0, 'TEST')
        self.assertIsNotNone(signal)
        self.assertAlmostEqual(signal['center_freq'], 100.0, delta=0.1)

    def generate_noise(self, num_samples):
        return (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)).astype(np.complex64)

    def generate_signal(self, freq, num_samples):
        t = np.arange(num_samples) / 20e6
        return (np.sin(2 * np.pi * (freq - 100.0) * 1e6 * t) * 100).astype(np.complex64)

if __name__ == '__main__':
    unittest.main()