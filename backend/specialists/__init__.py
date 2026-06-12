"""The six parallel safety specialists. Each reasons ONLY over retrieved passages and
emits findings with citation keys + severity. Registered in ALL for the pipeline.
"""

from __future__ import annotations

from . import allergies, boxed, contraindications, dose_special_population, duplication, interactions

ALL = [interactions, contraindications, allergies, duplication, dose_special_population, boxed]
