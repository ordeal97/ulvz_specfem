<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Third-party notices

`two_chunk_planner` is original ULVZ-project Python code distributed under
GPL-3.0-or-later.  Its runtime dependencies retain their own licenses and are
not relicensed by this package.

| Component | Role | License/source note |
| --- | --- | --- |
| NumPy | numerical arrays | See the NumPy distribution and its license files. |
| Matplotlib | static planner map | See the Matplotlib distribution and its license files. |
| PyYAML | strict YAML input parsing | See the PyYAML distribution and its license files. |
| ObsPy | optional TauP phase-aware paths | Optional dependency; see the ObsPy distribution and its license files. |
| geographiclib | geographic path support through ObsPy | Optional runtime support; see the geographiclib distribution and its license files. |
| SPECFEM3D_GLOBE | geometry/parameter behavior referenced by the canonical profile | Not bundled or executed by this package. Consult the separate SPECFEM3D_GLOBE license. |

The canonical profile records ULVZ project acceptance evidence as provenance;
it does not bundle SPECFEM source, the accepted patch, or third-party input
data. Copyright ownership of the original ULVZ-project planner code must be
confirmed by the project owner before distribution beyond this project.
