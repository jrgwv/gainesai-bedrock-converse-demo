import * as cdk from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";
import { BedrockStack } from "../lib/bedrock-stack";

describe("BedrockStack", () => {
  let template: Template;

  beforeEach(() => {
    const app = new cdk.App({ context: { env: "test" } });
    const stack = new BedrockStack(app, "TestStack", {
      env: { account: "123456789012", region: "us-east-1" },
    });
    template = Template.fromStack(stack);
  });

  test("creates Lambda with ARM64 architecture and X-Ray tracing", () => {
    template.hasResourceProperties("AWS::Lambda::Function", {
      Architectures: ["arm64"],
      Runtime: "python3.13",
      TracingConfig: { Mode: "Active" },
    });
  });

  test("Lambda is placed in a VPC", () => {
    template.hasResourceProperties("AWS::Lambda::Function", {
      VpcConfig: Match.objectLike({
        SubnetIds: Match.anyValue(),
      }),
    });
  });

  test("API Gateway has X-Ray tracing enabled", () => {
    template.hasResourceProperties("AWS::ApiGateway::Stage", {
      TracingEnabled: true,
    });
  });

  test("log group retains logs for one year", () => {
    template.hasResourceProperties("AWS::Logs::LogGroup", {
      RetentionInDays: 365,
    });
  });

  test("Lambda has Bedrock InvokeModel permission", () => {
    template.hasResourceProperties("AWS::IAM::Policy", {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: "bedrock:InvokeModel",
          }),
        ]),
      },
    });
  });

  test("Lambda has CloudWatch PutMetricData permission with nag suppression", () => {
    template.hasResourceProperties("AWS::IAM::Policy", {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: "cloudwatch:PutMetricData",
            Resource: "*",
          }),
        ]),
      },
    });
  });
});
