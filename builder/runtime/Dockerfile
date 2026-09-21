FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS codex

RUN npm install --global @openai/codex@0.153.4 \
    && npm cache clean --force \
    && test "$(codex --version)" = "codex-cli 0.153.4"

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
COPY --from=codex /usr/local/bin/node /usr/local/bin/node
COPY --from=codex /usr/local/lib/node_modules/@openai /usr/local/lib/node_modules/@openai
RUN ln -s /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex
COPY entry.py /opt/builder/entry.py
USER 1000:1000
ENV HOME=/work/home CODEX_HOME=/work/state TMPDIR=/tmp
WORKDIR /work
ENTRYPOINT ["python3", "-B", "/opt/builder/entry.py"]
