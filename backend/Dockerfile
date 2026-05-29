# builder — installs deps into /install and trims bytecode caches /
# bundled test suites that ship inside some third-party wheels. dist-info
# directories are preserved because importlib.metadata reads them at runtime.
FROM public.ecr.aws/lambda/python:3.13 AS builder
WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target /install . && \
    find /install -depth -type d -name __pycache__ -exec rm -rf {} + && \
    find /install -depth -type d \( -name tests -o -name test \) -exec rm -rf {} +

# runtime — copy only what Lambda needs
FROM public.ecr.aws/lambda/python:3.13
COPY --from=builder /install ${LAMBDA_TASK_ROOT}/
COPY src/ ${LAMBDA_TASK_ROOT}/

# Run as non-root; Lambda base image provides the "nobody" user
USER nobody

CMD ["api.handler"]
