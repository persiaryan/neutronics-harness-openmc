Implement the OpenMC calculation specified below.

Delivery contract: `openmc-model-factory-v1`.
Return only the complete Python source of one self-contained module, with no
Markdown fences or surrounding explanation. It will be saved as `candidate.py`.
Expose a callable `build_model()` that can be called without arguments and returns
one `openmc.Model` containing the task's materials, geometry and settings. A return
annotation is optional. Helper functions, names, IDs and valid alternative model
representations are your choice; materials may be inferred from geometry.

Use OpenMC 0.15.3. Python's standard library and NumPy are available. Obtain the
nuclear-data index from `OPENMC_CROSS_SECTIONS` in the execution environment;
do not hard-code an absolute path or download data. The execution environment
provides an ENDF/B-VIII.1 collection containing the required tables. Submit a single
module, without additional bundled resources or dependencies.

The execution driver imports your module, calls `build_model()` once, checks its
return value and exports that returned object using
`openmc.Model.export_to_model_xml(..., path='/work/model.xml')`. It uses a fresh
working directory. Do not export files or launch transport during import or
construction. Ordinary definitions, helpers and in-memory initialization are
allowed; leave no persistent filesystem changes during those phases. Child
process launches and observable XML/HDF5 writes in those phases are rejected.
The driver owns export; do not return previously written XML or rely on a model
stored elsewhere. There is no script-execution fallback or search for other models.

An optional `if __name__ == '__main__':` block for manual use is allowed; the
evaluator will not execute it. Transport is performed separately from the admitted
combined `model.xml`; split XML files are not the delivery format.

Do not include a guessed numerical answer. Implement the stated physical and
numerical inputs without adding unspecified components or adjusting them to
obtain a particular eigenvalue.

Task specification:

{{TASK_SPECIFICATION}}
