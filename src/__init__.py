"""Polymarket Pricing Gap Detection System."""

__version__ = "1.0.0"
__author__ = "Polymarket Gap Detector Team"
__description__ = "Multi-agent system for detecting pricing inefficiencies in Polymarket prediction markets"

from .main import PolymarketGapDetector, main

__all__ = ['PolymarketGapDetector', 'main']
