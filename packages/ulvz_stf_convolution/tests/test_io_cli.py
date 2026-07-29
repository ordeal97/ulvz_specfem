from __future__ import annotations

import numpy as np
import pytest

from ulvz_stf_convolution.cli import main
from ulvz_stf_convolution.convolution import convolve_waveform
from ulvz_stf_convolution.io import read_waveform, write_waveform
from ulvz_stf_convolution.stf import builtin_stf


def test_ascii_round_trip_cli_dry_run_and_overwrite_protection(tmp_path, capsys) -> None:
    source = tmp_path / "input.sem.ascii"
    source.write_text("0 1\n0.1 2\n0.2 3\n0.3 4\n", encoding="utf-8")
    output = tmp_path / "out.txt"
    assert main(["--input", str(source), "--output", str(output), "--stf-kind", "gaussian", "--half-duration", "0.1", "--dry-run"]) == 0
    assert not output.exists()
    assert main(["--input", str(source), "--output", str(output), "--stf-kind", "gaussian", "--half-duration", "0.1"]) == 0
    assert output.exists()
    assert main(["--input", str(source), "--output", str(output), "--stf-kind", "gaussian", "--half-duration", "0.1"]) == 2
    assert main(["--input", str(source), "--output", str(source), "--stf-kind", "gaussian", "--half-duration", "0.1", "--overwrite"]) == 2
    assert '"method"' in capsys.readouterr().err


def test_cli_numeric_stf_normalizes_and_writes_full_output(tmp_path) -> None:
    source = tmp_path / "base.sem.ascii"
    source.write_text("0 10\n0.1 0\n0.2 0\n", encoding="utf-8")
    stf_file = tmp_path / "moment_rate.txt"
    stf_file.write_text("-0.1 0\n0 2\n0.1 0\n", encoding="utf-8")
    output = tmp_path / "custom.sem.ascii"
    assert main([
        "--input", str(source), "--output", str(output), "--stf-kind", "numeric",
        "--stf-file", str(stf_file), "--mode", "full", "--method", "direct",
    ]) == 0
    result = read_waveform(output)
    assert result.times.tolist() == pytest.approx([-0.1, 0.0, 0.1, 0.2, 0.3])
    assert np.trapezoid(result.amplitudes, result.times) == pytest.approx(1.0)


def test_sac_same_and_full_round_trip_headers(tmp_path) -> None:
    obspy = pytest.importorskip("obspy")
    from obspy.io.sac import SACTrace

    source = tmp_path / "XX.TEST..BHZ.sem.sac"
    sac = SACTrace(data=np.array([1, 2, 3, 4], dtype=np.float32), delta=0.1, b=2.5,
                   nzyear=2020, nzjday=2, nzhour=3, nzmin=4, nzsec=5, nzmsec=0,
                   kstnm="TEST", kcmpnm="BHZ")
    sac.write(str(source))
    waveform = read_waveform(source, format="sac")
    stf = builtin_stf("gaussian", 0.1, waveform.dt)
    same = convolve_waveform(waveform, stf, mode="same")
    same_path = tmp_path / "same.sac"
    write_waveform(same.waveform, same_path, format="sac")
    same_read = read_waveform(same_path, format="sac")
    assert same_read.times[0] == pytest.approx(waveform.times[0])
    assert same_read.sac_trace.stats.starttime == waveform.sac_trace.stats.starttime
    assert same_read.sac_trace.stats.sac.kstnm == "TEST"
    assert same_read.sac_trace.stats.sac.kcmpnm == "BHZ"
    ascii_path = tmp_path / "same.ascii"
    np.savetxt(ascii_path, np.column_stack((waveform.times, waveform.amplitudes)))
    ascii_result = convolve_waveform(read_waveform(ascii_path), stf, mode="same")
    np.testing.assert_allclose(ascii_result.waveform.amplitudes, same_read.amplitudes, rtol=2e-6, atol=2e-6)

    full = convolve_waveform(waveform, stf, mode="full")
    full_path = tmp_path / "full.sac"
    write_waveform(full.waveform, full_path, format="sac")
    full_read = read_waveform(full_path, format="sac")
    assert full_read.times[0] == pytest.approx(full.waveform.times[0])
    assert full_read.sac_reference_time == waveform.sac_reference_time
    assert full_read.sac_trace.stats.npts == full.waveform.amplitudes.size
