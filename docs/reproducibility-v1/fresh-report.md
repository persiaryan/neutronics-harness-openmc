# Public native pin-cell reproduction

Protocol: `factory-assessment-boundaries-v4-temperature-source-v1`.
Status: **assessed**; retained-evidence review: **coherent**.
Verified protocol success: **True**.
Factory contract passed: **True**; native completion: **True**.
Final XML: `7111a76153e486871cc0df4f5954bbd9661e0d1dc8953b3e6d327d4fd1463011`.

| Check category | Results |
|---|---|
| geometry | {"boundaries": true, "domain": true, "extent_and_map": true, "interfaces": true} |
| materials | {"composition": true, "density": true, "temperature": true, "thermal_scattering": true} |
| physics_settings | {"entropy_mesh_and_output": true, "physics": true, "sampling": true, "source": true} |
| keff | {"equivalence_demonstrated": true} |
| statistical_quality | {"entropy_screen": true, "precision": true} |
| engineering_consistency | {"leakage_boundary_consistency": true, "leakage_probability": true} |

Candidate k-effective: {"mean": 1.4481972350919354, "std_dev": 0.0003414972628200393, "uncertainty": "one sigma"}.
Public reference k-effective: {"mean": 1.4488925454032306, "std_dev": 0.00016175366894689348, "uncertainty": "one sigma"}.
Numerical comparison: {"delta_pcm": -69.53103112952164, "combined_sigma_pcm": 37.78685352491792, "standardized_difference": -1.8400852318563792, "interval_pcm": [-143.59326403836076, 4.531201779317485], "margin_pcm": 150.0, "status": "agreement"}.

Identities and execution details are in report.json.

- One public handwritten computational example; no LLM invocation or historical study replay.
- Same existing scoring and uncalibrated +/-150 pcm criterion; grading activation remains disabled.
- Finite geometry/boundary observations; shared model/data biases and unproven convergence remain.
- The public reference emitted a Zr96 probability-table warning at 294 K; its shared-data bias is not quantified.
- Exact numerical reruns are only claimed for the same local runtime, data and seed after testing.
- Raw local assessment receipts can contain host paths; share report.json/report.md only.
