# gainsai-bedrock-converse-demo

Portable multi-model inference platform built on the Amazon Bedrock Converse API.
A FastAPI backend (deployed as a container Lambda behind API Gateway) routes
each request to the appropriate Claude model with automatic fallback.

## Deployment

### Default — new VPC

```bash
cd infra
npm ci
npx cdk deploy --context env=dev
```

The stack provisions a new VPC with NAT gateways, VPC flow logs, and interface
endpoints for `bedrock-runtime` and `bedrock`. No additional setup required.

### Existing VPC

If you supply `vpcId`, the stack imports that VPC instead of creating one. **You
are responsible for provisioning everything the Lambda needs to reach the AWS
services it calls** — the stack only creates the Lambda, API Gateway, and IAM.

```bash
npx cdk deploy --context env=dev --context vpcId=vpc-0abc1234
```

Or programmatically:

```ts
new BedrockStack(app, "BedrockConverse-prod", {
  env: { account, region },
  existingVpcId: "vpc-0abc1234",
});
```

#### VPC requirements for the existing-VPC path

| Requirement | Why |
|---|---|
| At least two private subnets across two AZs with available IPs | Lambda ENIs need free IPs; multi-AZ is required for the reserved-concurrency setting |
| `enableDnsHostnames = true` and `enableDnsSupport = true` | Private DNS resolution for the VPC interface endpoints below |
| NAT gateway **or** complete VPC endpoint coverage (see below) | The Lambda must be able to reach every AWS service it calls |

#### AWS service endpoints the Lambda calls

If the VPC has a NAT gateway with public egress, none of these are strictly
required (Lambda will reach the public AWS endpoints). For a fully private VPC
(no NAT), provision interface endpoints for all of them:

| Service | Endpoint | Used for |
|---|---|---|
| Bedrock data plane | `com.amazonaws.<region>.bedrock-runtime` | `InvokeModel` / Converse calls |
| Bedrock control plane | `com.amazonaws.<region>.bedrock` | Optional — model + inference-profile metadata |
| CloudWatch Logs | `com.amazonaws.<region>.logs` | Lambda execution logs, API Gateway access logs |
| CloudWatch Metrics | `com.amazonaws.<region>.monitoring` | `cloudwatch:PutMetricData` from `observability.py` |
| X-Ray | `com.amazonaws.<region>.xray` | Active tracing on Lambda + API Gateway |
| ECR API | `com.amazonaws.<region>.ecr.api` | Pulling the Lambda container image at init |
| ECR Docker | `com.amazonaws.<region>.ecr.dkr` | Pulling the Lambda container image at init |
| S3 (gateway endpoint) | `com.amazonaws.<region>.s3` | ECR stores image layers in S3; gateway endpoint is free |

All interface endpoints should have `PrivateDnsEnabled = true` so the SDK
resolves the standard service hostnames to the endpoint ENIs.

Each interface endpoint also needs a security group allowing TCP 443 from
the Lambda's security group (or from the VPC CIDR, which is what
`addInterfaceEndpoint` does by default).

#### What the stack does NOT create on the existing-VPC path

- VPC flow logs — assumed to be managed by the VPC owner
- NAT gateways
- Interface or gateway endpoints (the table above)
- Route tables or subnets

The stack still applies its CloudWatch logging, X-Ray tracing, and IAM
configuration; only networking is left to the VPC owner.

## Quality gates

```bash
./scripts/lint.sh      # ruff + mypy + prettier + eslint
./scripts/security.sh  # bandit + pip-audit + semgrep
./scripts/test.sh      # pytest + jest
```

See `CLAUDE.md` for branch strategy, full tooling versions, and CI details.

## Troubleshooting

### Podman drops the ECR push partway through

Symptom: `cdk deploy` reports a network error or hang while publishing
the Lambda container image to ECR, somewhere around the multi-hundred-MB
mark. Re-running `cdk deploy` succeeds, sometimes after 2–3 attempts.

Cause: a known issue with Podman's ECR push path where its HTTP/2 → HTTP/1
fallback fails on long-running uploads against ECR. The image is partially
uploaded; the next `cdk deploy` resumes from the last successfully pushed
layer, so retries make progress each time.

Workarounds, best to worst:
1. Use Docker Desktop or `colima` (Docker-compatible) locally — no connection-drop issue.
2. Run the deploy from CI (GitHub Actions runners use Docker by default).
3. Re-run `cdk deploy` 2–3 times until it succeeds (each retry pushes more layers).

### Container image is large

The runtime image is roughly 600 MB. About 480 MB of that is the
`public.ecr.aws/lambda/python:3.13` base image, which is fixed. The
Dockerfile strips `__pycache__/` and bundled `tests/` directories from
installed dependencies, and `uvicorn[standard]` is held out as a dev-only
dep (Lambda uses Mangum for ASGI bridging — uvicorn isn't imported at
runtime). Further shrinkage is possible but requires pruning
`botocore/data/` to only the services this Lambda uses, which is fragile.
