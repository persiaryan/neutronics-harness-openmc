ARG DEPENDENCY_IMAGE
FROM ${DEPENDENCY_IMAGE} AS dependencies
FROM python@sha256:d04f49f5882f49a3b91f874e75e19f0c265f7222da8659741a9d7eab148f22a9
# Only installed third-party dependencies cross from the reviewed local image.
# No /opt/nh code, model, reference, nuclear data, or build evidence is copied.
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
RUN --network=none python -I -B -c "import openmc; assert openmc.__version__ == '0.15.3'"
COPY idle.py probe.py /opt/evaluator/
USER 1000:1000
ENV HOME=/tmp/home TMPDIR=/tmp MPLCONFIGDIR=/tmp/mpl OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /work
ENTRYPOINT ["python", "-I", "-B", "/opt/evaluator/idle.py"]
