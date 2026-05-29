# builder — installs deps into /install
FROM public.ecr.aws/lambda/python:3.13 AS builder
WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target /install .

# runtime — copy only what Lambda needs
FROM public.ecr.aws/lambda/python:3.13
COPY --from=builder /install ${LAMBDA_TASK_ROOT}/
COPY src/ ${LAMBDA_TASK_ROOT}/

# Run as non-root; Lambda base image provides the "nobody" user
USER nobody

CMD ["api.handler"]
