Shared guided construction/export policy: guided-construction-v1.
Before final submission, you MUST save your current factory as candidate.py in
/work/workspace and actually attempt to call build_model() and export its returned
model using your execution tool. Do not wait for a successful export to decide
whether to attempt construction. Keep import and build_model() free of export
side effects; the scratch command below exports only after build_model() returns.

Run this scratch command from /work/workspace. The empty index is an explicit
local placeholder for XML authoring only; it neither supplies nor validates
nuclear data. Keep the submitted module reading OPENMC_CROSS_SECTIONS from its
execution environment, without embedding this scratch path or fallback data.

```sh
timeout 60s python3 -B - <<'PY'
import os
from pathlib import Path
Path('model.xml').unlink(missing_ok=True)
index = Path('scratch-cross_sections.xml').resolve()
index.write_text('<cross_sections/>\n')
os.environ['OPENMC_CROSS_SECTIONS'] = str(index)
import openmc
from candidate import build_model
model = build_model()
if not isinstance(model, openmc.Model):
    raise TypeError('build_model() must return openmc.Model')
model.export_to_model_xml(path='model.xml')
print('WORKING_EXPORT_OK')
PY
```

Read the real execution output, including errors. If a command is still running,
collect its completion before deciding what happened. If construction/export
fails and resources remain, attempt one justified repair and rerun the scratch
command. At most one construction/export repair attempt is allowed per session;
do not retry until success. If export remains unsuccessful, state the actual
blocker in an authoring message and in a brief Python comment in the final source.
Do not claim a successful export when execution failed.


Re-export after any model change. Keep the complete execution result, including
exit_code and output, visible in the tool response; collect completion for a
running command. Use the same eight-request / 600-second ceiling. No automatic
retries or extra requests. If resources prevent the workflow, disclose which
steps remain undone. Finally return only the complete factory source, without
Markdown (brief status comments are allowed). Never run native transport.
