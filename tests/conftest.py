"""pytest configuration and shared fixtures."""
import sys
import os
from pathlib import Path

# Add project root to Python path so tests can import backend/ingestion/etc.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
