<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Optional external Par_file example

This small text fixture may live at any path. It is not a complete production
SPECFEM `Par_file`, does not identify a SPECFEM checkout, and does not verify
an accepted patch. It only lets the standalone planner read NEX/NPROC and
resource-compatibility flags.

~~~bash
P=packages/two_chunk_planner
PY=${ULVZ_PYTHON:-python3}
PYTHONPATH=$P/src "$PY" -m two_chunk_planner plan \
  --cmtsolution $P/examples/geometry_only/DATA/CMTSOLUTION \
  --stations $P/examples/geometry_only/DATA/STATIONS \
  --par-file $P/examples/external_par_file/Par_file --analysis-window 0 1900 \
  --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output /tmp/two_chunk_external_par_example
~~~

Choose a new, nonexistent `--output` directory for each run.
