You are working in a SPECFEM3D_GLOBE repository for synthetic ULVZ waveform modeling.

Do not modify any source code, model file, Makefile, Par_file, or simulation input.
Do not run mesh generation or forward simulations.
This is an audit-only task.

Goal:
Determine how S40RTS and SPiRaL are loaded and evaluated in this exact local SPECFEM version, and assess how an analytical CMB ULVZ could later be superimposed while preserving the original background tomography.

Inspect at least:

* src/meshfem3D/model_s20rts.f90
* src/meshfem3D/model_s40rts.f90
* src/meshfem3D/model_spiral.f90
* src/meshfem3D/get_model_parameters.f90
* all files that select MODEL names, call the model routines, or add mantle discontinuity topography
* DATA/s40rts/, DATA/s20rts/, and DATA/spiral1.4/ if present
* the project user manual or local documentation on changing S20RTS-like models

First record:

* git commit or release version;
* whether SPiRaL model data are installed locally;
* the precise MODEL strings needed for S40RTS and SPiRaL;
* the source files and line numbers supporting every conclusion.

Create:
docs/model_reader_comparison_s40rts_spiral.md

The report must contain the following sections.

1. Call-path diagram
   Trace the path from MODEL in DATA/Par_file to the actual mantle-model routine used during mesh generation for:

* s20rts
* s40rts
* spiral

Include all model-selection flags and relevant broadcast routines.

2. S20RTS versus S40RTS
   Compare:

* input files and their formats;
* spherical-harmonic degree;
* radial basis functions and radial domain;
* whether model values are absolute or relative;
* how dVs, dVp, and dRho are determined;
* reference model and crustal-model handling;
* MPI reading and broadcasting;
* routine input/output signatures and units.

State explicitly whether the S20RTS ULVZ-overlay strategy can be transferred directly to S40RTS, and identify the exact routine and logical position where an overlay should later be applied.

3. SPiRaL reading and interpolation
   Determine:

* all mantle, crust, density, elastic-coefficient, and discontinuity-topography files read by SPiRaL;
* whether SPiRaL mantle values are absolute or perturbations;
* the physical meaning and units of C11, C13, C33, C44, C66, and density;
* the latitude, longitude, radius/depth, and unit conventions;
* the horizontal and radial interpolation actually implemented in this local source version;
* whether 410 km and 660 km discontinuity topography changes the mesh;
* how radial anisotropy is represented;
* where model values are non-dimensionalized and rotated into the global coordinate frame.

Do not fix suspected implementation issues. Report them separately as observations, with file and line references.

4. ULVZ implementation options
   Compare two approaches for each background model:
   A. Modify the original external model data files.
   B. Keep all original tomography files unchanged and apply an analytical ULVZ overlay inside the model-evaluation routine.

For each approach discuss:

* reproducibility;
* risk of corrupting the original model;
* support for arbitrary ULVZ geometry and smooth boundaries;
* compatibility with parameter sweeps;
* need for recompilation;
* whether it preserves the original background model outside the ULVZ.

Recommend one approach for S40RTS and one for SPiRaL.

5. Required parameter convention before implementation
   State that the future ULVZ must define whether dVp, dVs, and dRho are relative to:
   A. the 1-D reference model, or
   B. the local tomographic background value.

Explain the resulting combination rule for each interpretation.

For SPiRaL, evaluate two scientifically distinct options:
A. preserve its radial anisotropy while applying the same fractional P- and S-wave perturbations to vertical and horizontal velocities;
B. replace the material inside the ULVZ with an isotropic material.

Do not choose silently. Explain the physical and coding consequences of both options.

6. Proposed implementation design
   Without writing code, propose a minimal architecture that:

* shares a common ULVZ geometry and taper definition across S40RTS and SPiRaL;
* avoids duplicating the ULVZ geometry logic;
* keeps the existing s40rts and spiral implementations untouched;
* introduces clearly named model variants such as s40rts_ulvz and spiral_ulvz;
* identifies all source/build files that would eventually need changes.

Finish with:

* a concise comparison table;
* a list of unresolved questions;
* a recommended next task named “Task 3B: implement ULVZ overlay for S40RTS only”.

Confirm at the end that no files outside docs/model_reader_comparison_s40rts_spiral.md were changed.
