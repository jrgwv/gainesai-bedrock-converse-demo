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

  describe("with existingVpcId", () => {
    const account = "123456789012";
    const region = "us-east-1";
    const vpcId = "vpc-12345";
    const lookupKey = `vpc-provider:account=${account}:filter.vpc-id=${vpcId}:region=${region}:returnAsymmetricSubnets=true`;
    const lookupResult = {
      vpcId,
      vpcCidrBlock: "10.0.0.0/16",
      availabilityZones: [],
      subnetGroups: [
        {
          name: "Private",
          type: "Private",
          subnets: [
            {
              subnetId: "subnet-aaa",
              cidr: "10.0.1.0/24",
              availabilityZone: "us-east-1a",
              routeTableId: "rtb-aaa",
            },
            {
              subnetId: "subnet-bbb",
              cidr: "10.0.2.0/24",
              availabilityZone: "us-east-1b",
              routeTableId: "rtb-bbb",
            },
          ],
        },
      ],
    };

    let importedTpl: Template;

    beforeEach(() => {
      const app = new cdk.App({
        context: {
          env: "test",
          [lookupKey]: lookupResult,
        },
      });
      const stack = new BedrockStack(app, "ImportedVpcStack", {
        env: { account, region },
        existingVpcId: vpcId,
      });
      importedTpl = Template.fromStack(stack);
    });

    test("does not create a new VPC", () => {
      importedTpl.resourceCountIs("AWS::EC2::VPC", 0);
    });

    test("does not create VPC flow logs", () => {
      importedTpl.resourceCountIs("AWS::EC2::FlowLog", 0);
    });

    test("places Lambda in the imported subnets", () => {
      importedTpl.hasResourceProperties("AWS::Lambda::Function", {
        VpcConfig: Match.objectLike({
          SubnetIds: Match.arrayWith(["subnet-aaa", "subnet-bbb"]),
        }),
      });
    });
  });
});
