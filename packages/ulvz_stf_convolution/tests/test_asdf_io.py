from __future__ import annotations

import h5py
import numpy as np
import pytest

from ulvz_stf_convolution.asdf import read_asdf_waveforms, write_asdf_waveforms
from ulvz_stf_convolution.cli import main
from ulvz_stf_convolution.convolution import convolve_waveform
from ulvz_stf_convolution.errors import StfConvolutionError
from ulvz_stf_convolution.stf import builtin_stf, fortran_compatible_stf


START_NS = 1_600_000_000_000_000_000


def _synthetic_asdf(path, *, standard_names: bool = True) -> None:
    with h5py.File(path, "w") as handle:
        handle.attrs["file_format"] = "ASDF"
        handle.attrs["file_format_version"] = "1.0.0"
        handle.create_dataset("QuakeML", data=np.bytes_("<event/>"))
        handle.create_dataset("AuxiliaryData/unchanged", data=np.array([7], dtype=np.int16))
        station = handle.create_group("Waveforms/XX.TEST")
        station.create_dataset("StationXML", data=np.bytes_("<station/>"))
        for component, values in (("BHZ", [1, 2, 3, 4]), ("BHN", [4, 3, 2, 1])):
            if standard_names:
                name = f"XX.TEST.S3.{component}__2020-09-13T12:26:40__2020-09-13T12:26:40__synthetic"
            else:
                name = component
            dataset = station.create_dataset(name, data=np.asarray(values, dtype=np.float32))
            dataset.attrs["sampling_rate"] = 10.0
            dataset.attrs["starttime"] = np.int64(START_NS)
            dataset.attrs["event_id"] = "smi:local/event"


def test_asdf_same_round_trip_preserves_nonwaveform_content(tmp_path) -> None:
    source = tmp_path / "synthetic.h5"
    output = tmp_path / "same.h5"
    _synthetic_asdf(source)

    traces = read_asdf_waveforms(source)
    assert len(traces) == 2
    assert {trace.asdf_dataset_path for trace in traces} == {
        "/Waveforms/XX.TEST/XX.TEST.S3.BHN__2020-09-13T12:26:40__2020-09-13T12:26:40__synthetic",
        "/Waveforms/XX.TEST/XX.TEST.S3.BHZ__2020-09-13T12:26:40__2020-09-13T12:26:40__synthetic",
    }
    results = [convolve_waveform(trace, builtin_stf("gaussian", 0.1, trace.dt), mode="same") for trace in traces]
    write_asdf_waveforms(source, output, [result.waveform for result in results])

    with h5py.File(source, "r") as original, h5py.File(output, "r") as written:
        assert original["QuakeML"][()] == written["QuakeML"][()]
        np.testing.assert_array_equal(original["AuxiliaryData/unchanged"][...], written["AuxiliaryData/unchanged"][...])
        assert original["Waveforms/XX.TEST/StationXML"][()] == written["Waveforms/XX.TEST/StationXML"][()]
        assert set(original["Waveforms/XX.TEST"].keys()) == set(written["Waveforms/XX.TEST"].keys())
        for trace, result in zip(traces, results, strict=True):
            original_data = original[trace.asdf_dataset_path][...]
            assert np.array_equal(original_data, trace.amplitudes.astype(np.float32))
            written_trace = written[trace.asdf_dataset_path]
            assert written_trace.attrs["starttime"] == START_NS
            assert written_trace.attrs["event_id"] == "smi:local/event"
            np.testing.assert_allclose(written_trace[...], result.waveform.amplitudes, rtol=2e-6, atol=2e-6)


@pytest.mark.parametrize("mode", ("full", "fortran"))
def test_asdf_length_changing_modes_update_time_metadata_and_do_not_change_input(tmp_path, mode) -> None:
    source = tmp_path / "synthetic.h5"
    output = tmp_path / f"{mode}.h5"
    _synthetic_asdf(source)
    traces = read_asdf_waveforms(source)
    results = [
        convolve_waveform(
            trace,
            fortran_compatible_stf("triangle", 0.1, trace.dt) if mode == "fortran" else builtin_stf("triangle", 0.1, trace.dt),
            mode=mode,
        )
        for trace in traces
    ]
    write_asdf_waveforms(source, output, [result.waveform for result in results])

    with h5py.File(source, "r") as original, h5py.File(output, "r") as written:
        assert set(original["Waveforms/XX.TEST"].keys()) >= {"StationXML"}
        for old_trace, result in zip(traces, results, strict=True):
            assert old_trace.asdf_dataset_path in original
            prefix = old_trace.asdf_dataset_path.rsplit("/", 1)[-1].split("__", 1)[0]
            new_trace = next(
                trace for trace in read_asdf_waveforms(output)
                if trace.asdf_dataset_path.rsplit("/", 1)[-1].startswith(prefix + "__")
            )
            if mode == "full":
                assert old_trace.asdf_dataset_path not in written
            else:
                # SPECFEM writes dataset labels with second precision. This short
                # fixture's trimmed end still falls in the original second.
                assert new_trace.asdf_dataset_path == old_trace.asdf_dataset_path
            assert new_trace.asdf_starttime_ns == START_NS + int(round(result.waveform.times[0] * 1.0e9))
            assert len(new_trace.amplitudes) == len(result.waveform.amplitudes)
            np.testing.assert_allclose(new_trace.amplitudes, result.waveform.amplitudes, rtol=2e-6, atol=2e-6)


def test_asdf_cli_dry_run_and_full_file_output(tmp_path) -> None:
    source = tmp_path / "synthetic.h5"
    output = tmp_path / "convolved.h5"
    _synthetic_asdf(source)
    arguments = [
        "--input", str(source), "--output", str(output), "--input-format", "asdf",
        "--stf-kind", "gaussian", "--half-duration", "0.1",
    ]
    assert main([*arguments, "--dry-run"]) == 0
    assert not output.exists()
    assert main(arguments) == 0
    assert len(read_asdf_waveforms(output)) == 2


def test_asdf_full_rejects_non_specfem_dataset_name(tmp_path) -> None:
    source = tmp_path / "synthetic.h5"
    _synthetic_asdf(source, standard_names=False)
    traces = read_asdf_waveforms(source)
    results = [convolve_waveform(trace, builtin_stf("triangle", 0.1, trace.dt), mode="full") for trace in traces]
    with pytest.raises(StfConvolutionError, match="non-SPECFEM name"):
        write_asdf_waveforms(source, tmp_path / "output.h5", [result.waveform for result in results])
