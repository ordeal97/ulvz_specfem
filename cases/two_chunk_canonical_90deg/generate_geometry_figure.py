#!/usr/bin/env python3
"""Generate source-controlled SVG figures for the canonical two-chunk guide.

The figures are explanatory schematics, not mesh output or map projections.
They encode the geometry and gamma convention verified against the current
SPECFEM source and the project acceptance records.
"""

from __future__ import annotations

import argparse
from pathlib import Path


GEOMETRY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="670" viewBox="0 0 1200 670" role="img" aria-labelledby="title desc">
<title id="title">Canonical two-chunk local topology and gamma convention</title>
<desc id="desc">The left panel shows central chunk AB and supported-left chunk AC. Their shared internal xi face has endpoints C1 eta-min and C2 eta-max and is never absorbing. The right panel shows a tangent-plane view from outside the Earth; positive gamma is counter-clockwise from North.</desc>
<style>
 text{font-family:Arial,'Noto Sans CJK SC',sans-serif;fill:#14213d}.title{font-size:23px;font-weight:bold}.label{font-size:18px;font-weight:bold}.small{font-size:15px}.tiny{font-size:13px}.box{fill:#fff;stroke:#14213d;stroke-width:2}.internal{fill:none;stroke:#d62828;stroke-width:4;stroke-dasharray:10 7}.axis{fill:none;stroke:#1d3557;stroke-width:3;marker-end:url(#navy)}.gamma{fill:none;stroke:#e76f00;stroke-width:4;marker-end:url(#orange)}.note{fill:#fff6df;stroke:#e76f00;stroke-width:1.5}.external{stroke:#2a9d8f;stroke-width:5}.panel{fill:#f8fbff;stroke:#8aa4bd;stroke-width:2}
</style>
<defs>
 <marker id="navy" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#1d3557"/></marker>
 <marker id="orange" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#e76f00"/></marker>
</defs>
<rect x="22" y="22" width="1156" height="626" rx="12" fill="#fff" stroke="#14213d" stroke-width="2"/>
<text x="48" y="58" class="title">Canonical 90° two-chunk geometry: local topology is not a geographic map</text>
<rect x="46" y="84" width="636" height="520" rx="10" class="panel"/>
<text x="70" y="118" class="label">A. Unrotated local topology (attachment definition)</text>
<rect x="92" y="174" width="242" height="294" rx="5" fill="#dff2e1" class="box"/>
<rect x="334" y="174" width="242" height="294" rx="5" fill="#dceefa" class="box"/>
<text x="145" y="211" class="label">AC / chunk 2</text><text x="130" y="234" class="small">supported-left attachment</text>
<text x="394" y="211" class="label">AB / chunk 1</text><text x="392" y="234" class="small">central chunk</text>
<line x1="334" y1="174" x2="334" y2="468" class="internal"/>
<text x="306" y="324" class="tiny" transform="rotate(-90 306 324)">shared internal interface</text>
<circle cx="334" cy="468" r="7" fill="#d62828"/><text x="346" y="493" class="label">C1 = eta-min endpoint</text>
<circle cx="334" cy="174" r="7" fill="#d62828"/><text x="346" y="161" class="label">C2 = eta-max endpoint</text>
<line x1="455" y1="322" x2="546" y2="322" class="axis"/><text x="554" y="327" class="small">AB +xi</text>
<line x1="455" y1="322" x2="455" y2="249" class="axis"/><text x="464" y="252" class="small">AB +eta</text>
<line x1="213" y1="322" x2="121" y2="322" class="axis"/><text x="98" y="327" class="small">AC +xi</text>
<line x1="213" y1="322" x2="213" y2="249" class="axis"/><text x="222" y="252" class="small">AC +eta</text>
<line x1="92" y1="174" x2="334" y2="174" class="external"/><line x1="92" y1="468" x2="334" y2="468" class="external"/><line x1="92" y1="174" x2="92" y2="468" class="external"/>
<line x1="576" y1="174" x2="576" y2="468" class="external"/><line x1="334" y1="174" x2="576" y2="174" class="external"/><line x1="334" y1="468" x2="576" y2="468" class="external"/>
<rect x="84" y="515" width="510" height="60" rx="6" class="note"/>
<text x="100" y="540" class="small">Dashed red: MPI field exchange only — never sponge or Stacey.</text>
<text x="100" y="562" class="small">Green solid faces: exposed external faces eligible for regional Stacey roles.</text>
<rect x="712" y="84" width="442" height="520" rx="10" class="panel"/>
<text x="736" y="118" class="label">B. Whole-system orientation (tangent-plane view)</text>
<text x="736" y="141" class="small">View from outside Earth looking down at the central point.</text>
<circle cx="933" cy="337" r="136" fill="#eef5fb" stroke="#8aa4bd" stroke-width="2"/>
<circle cx="933" cy="337" r="7" fill="#111"/><text x="946" y="357" class="small">central point</text>
<line x1="933" y1="337" x2="933" y2="185" class="axis"/><text x="942" y="190" class="label">North</text>
<line x1="933" y1="337" x2="1085" y2="337" class="axis"/><text x="1040" y="328" class="label">East</text>
<line x1="933" y1="337" x2="933" y2="222" class="axis"/><text x="944" y="245" class="small">gamma=0: +eta</text>
<line x1="933" y1="337" x2="1046" y2="337" class="axis"/><text x="966" y="323" class="small">gamma=0: +xi</text>
<path d="M933,166 A171,171 0 0 0 762,337" class="gamma"/>
<text x="748" y="235" class="label" fill="#e76f00">+gamma</text><text x="735" y="256" class="small">counter-clockwise from North</text>
<rect x="745" y="488" width="380" height="83" rx="6" class="note"/>
<text x="760" y="512" class="small">gamma 0°: +eta North, +xi East</text>
<text x="760" y="534" class="small">gamma 90°: +eta West, +xi North</text>
<text x="760" y="556" class="small">gamma 180°: +eta South, +xi West</text>
<text x="48" y="630" class="tiny">Source basis: current Euler matrix (src/shared/euler_angles.f90), regional manual §5, accepted canonical fixture. AB/AC names denote cubed-sphere face roles, not compass directions.</text>
</svg>
"""


WORKFLOW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="420" viewBox="0 0 1180 420" role="img" aria-labelledby="title desc">
<title id="title">Canonical two-chunk user workflow</title><desc id="desc">A staged workflow from source and patch verification to mesh, databases, solver smoke test, and production validation. Red stop boxes identify conditions that must halt progression.</desc>
<style>text{font-family:Arial,'Noto Sans CJK SC',sans-serif;fill:#14213d}.title{font-size:23px;font-weight:bold}.step{font-size:16px;font-weight:bold}.small{font-size:13px}.box{fill:#eaf4fb;stroke:#1d3557;stroke-width:2}.stop{fill:#ffe4e4;stroke:#c1121f;stroke-width:2}.note{fill:#fff6df;stroke:#e76f00;stroke-width:1.5}.arrow{stroke:#1d3557;stroke-width:2.5;marker-end:url(#a)}</style><defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8z" fill="#1d3557"/></marker></defs>
<rect x="18" y="18" width="1144" height="384" rx="12" fill="#fff" stroke="#14213d" stroke-width="2"/><text x="42" y="54" class="title">Canonical two-chunk workflow: user run versus advanced acceptance</text>
<g><rect x="48" y="105" width="155" height="76" rx="8" class="box"/><text x="67" y="133" class="step">1. Verify source</text><text x="66" y="155" class="small">patch + hash/context</text></g>
<g><rect x="250" y="105" width="155" height="76" rx="8" class="box"/><text x="270" y="133" class="step">2. Prepare inputs</text><text x="267" y="155" class="small">90°/90°, source, stations</text></g>
<g><rect x="452" y="105" width="155" height="76" rx="8" class="box"/><text x="470" y="133" class="step">3. Pre-mesh audit</text><text x="475" y="155" class="small">geometry + margins</text></g>
<g><rect x="654" y="105" width="155" height="76" rx="8" class="box"/><text x="677" y="133" class="step">4. xmeshfem3D</text><text x="677" y="155" class="small">mesh + databases</text></g>
<g><rect x="856" y="105" width="155" height="76" rx="8" class="box"/><text x="873" y="133" class="step">5. xspecfem3D</text><text x="877" y="155" class="small">short solver smoke</text></g>
<line x1="203" y1="143" x2="250" y2="143" class="arrow"/><line x1="405" y1="143" x2="452" y2="143" class="arrow"/><line x1="607" y1="143" x2="654" y2="143" class="arrow"/><line x1="809" y1="143" x2="856" y2="143" class="arrow"/>
<rect x="57" y="239" width="276" height="74" rx="8" class="stop"/><text x="76" y="266" class="step">STOP</text><text x="76" y="288" class="small">hash/context mismatch, non-canonical geometry,</text><text x="76" y="306" class="small">or source/station outside domain</text><line x1="125" y1="181" x2="125" y2="239" class="arrow"/>
<rect x="371" y="239" width="308" height="74" rx="8" class="note"/><text x="389" y="266" class="step">Face-role rule</text><text x="389" y="288" class="small">AB–AC: internal MPI exchange; never sponge/Stacey.</text><text x="389" y="306" class="small">Only exposed outer faces use regional Stacey.</text><line x1="530" y1="181" x2="530" y2="239" class="arrow"/>
<rect x="721" y="239" width="392" height="74" rx="8" class="note"/><text x="739" y="266" class="step">Before production / publication</text><text x="739" y="288" class="small">Endpoint topology, Stacey roles, decomposition invariance,</text><text x="739" y="306" class="small">and physical-window waveform regression must pass.</text><line x1="934" y1="181" x2="934" y2="239" class="arrow"/>
<text x="48" y="364" class="small">Global sponge is rejected for NCHUNKS=2 by current source; use ABSORBING_CONDITIONS=.true. and ABSORB_USING_GLOBAL_SPONGE=.false. for exposed regional faces.</text>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--geometry-output", type=Path,
                        default=root / "docs/assets/two_chunk_canonical_geometry.svg")
    parser.add_argument("--workflow-output", type=Path,
                        default=root / "docs/assets/two_chunk_user_workflow.svg")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    outputs = ((args.geometry_output, GEOMETRY_SVG), (args.workflow_output, WORKFLOW_SVG))
    if args.dry_run:
        for output, _ in outputs:
            print(f"would write {output}")
        return 0
    for output, content in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
