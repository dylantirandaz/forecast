"""Data adapters for ingesting external NYC housing datasets."""

from .base import DataAdapter
from .dob_permits import DOBPermitAdapter
from .fred_data import FREDAdapter
from .hpd_complaints import HPDComplaintAdapter
from .nychvs import NYCHVSAdapter
from .pluto import PLUTOAdapter
from .rent_guidelines import RGBAdapter

__all__ = [
    "DataAdapter",
    "DOBPermitAdapter",
    "FREDAdapter",
    "HPDComplaintAdapter",
    "NYCHVSAdapter",
    "PLUTOAdapter",
    "RGBAdapter",
]
