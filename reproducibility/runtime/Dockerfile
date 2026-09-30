# Public source build: no repository-specific preloaded image.
FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS build
# A fixed Debian snapshot pins compiler, HDF5 and their system dependencies.
RUN rm /etc/apt/sources.list.d/debian.sources && \
    printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20251001T000000Z bookworm main\n' > /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends g++ cmake make git ca-certificates libhdf5-dev && \
    rm -rf /var/lib/apt/lists/*
RUN git clone --branch v0.15.3 --depth 1 https://github.com/openmc-dev/openmc.git /source && \
    cd /source && test "$(git rev-parse HEAD)" = 27e38e894697bb32a1dac7848d2618818b6b8daf && \
    git submodule update --init --depth 1 && \
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/openmc \
      -DOPENMC_USE_MPI=OFF -DOPENMC_USE_OPENMP=ON -DOPENMC_BUILD_TESTS=OFF -DOPENMC_FORCE_VENDORED_LIBS=ON && \
    cmake --build build --parallel 2 && cmake --install build && \
    mkdir /runtime-libs && ldd /opt/openmc/lib/libopenmc.so | awk '/=> \/.* \(/ {print $3}' | xargs -I '{}' cp -L '{}' /runtime-libs/
COPY reproducibility/runtime/requirements.txt /requirements.txt
RUN python -m pip install --no-cache-dir -r /requirements.txt && \
    python -m pip install --no-cache-dir --no-deps --no-build-isolation /source && \
    python -m pip check
# Export/observation image deliberately contains no native solver.
FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS export
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY evaluator/runtime/idle.py evaluator/runtime/probe.py /opt/evaluator/
RUN python -I -B -c "import openmc; assert openmc.__version__ == '0.15.3'"
USER 1000:1000
ENV HOME=/tmp/home TMPDIR=/tmp MPLCONFIGDIR=/tmp/mpl OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 HDF5_PLUGIN_PRELOAD=::
WORKDIR /work
ENTRYPOINT ["python", "-I", "-B", "/opt/evaluator/idle.py"]
FROM export AS transport
USER root
COPY --from=build /opt/openmc /opt/openmc
# The ldd-resolved shared-library closure comes from the same pinned base/snapshot.
COPY --from=build /runtime-libs/ /usr/lib/aarch64-linux-gnu/
COPY evaluator/runtime/transport_worker.py /opt/evaluator/
RUN /opt/openmc/bin/openmc --version
USER 1000:1000
