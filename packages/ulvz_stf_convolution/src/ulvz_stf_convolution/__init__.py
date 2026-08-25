"""Standalone source-time-function convolution for SPECFEM waveforms."""

from .asdf import output_dataset_paths, read_asdf_waveforms, write_asdf_waveforms
from .convolution import convolve_waveform
from .io import read_waveform, write_waveform
from .models import ConvolutionResult, SourceTimeFunction, Waveform
from .stf import builtin_stf, read_numeric_stf, resample_stf

__all__ = [
    "ConvolutionResult",
    "SourceTimeFunction",
    "Waveform",
    "builtin_stf",
    "convolve_waveform",
    "output_dataset_paths",
    "read_asdf_waveforms",
    "read_numeric_stf",
    "read_waveform",
    "resample_stf",
    "write_waveform",
    "write_asdf_waveforms",
]
