from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Waveform:
    """Uniformly sampled waveform using a numeric, relative time axis in seconds."""

    times: np.ndarray
    amplitudes: np.ndarray
    dt: float
    format: str
    path: Path | None = None
    sac_trace: Any | None = None
    sac_reference_time: Any | None = None


@dataclass(frozen=True)
class SourceTimeFunction:
    """Moment-rate samples and their physical times relative to source time zero."""

    times: np.ndarray
    amplitudes: np.ndarray
    kind: str
    original_integral: float
    normalized_integral: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConvolutionResult:
    waveform: Waveform
    mode: str
    method: str
    stf: SourceTimeFunction
    warnings: tuple[str, ...] = ()
