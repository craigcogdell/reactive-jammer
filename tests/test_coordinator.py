
import unittest
from unittest.mock import MagicMock, patch
import time
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from coordinator import Coordinator

class TestCoordinator(unittest.TestCase):
    def test_coordinator_initialization(self):
        coordinator = Coordinator(simulation=True)
        self.assertIsInstance(coordinator, Coordinator)
        self.assertFalse(coordinator.running)

if __name__ == '__main__':
    unittest.main()
