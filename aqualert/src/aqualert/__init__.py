"""Aqualert - edge AI leak detector for tank-type toilets.

The package is import-safe with no hardware present: GPIO libraries are
imported lazily only inside the real HC-SR04 driver, so the entire pipeline
runs in simulation mode on a laptop.
"""

__all__ = ["__version__"]
__version__ = "1.0.0"
