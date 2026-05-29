import * as cdk from "aws-cdk-lib";
import {
  aws_apigateway as apigw,
  aws_ec2 as ec2,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_logs as logs,
  RemovalPolicy,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import { AwsSolutionsChecks, NagSuppressions } from "cdk-nag";

export class BedrockStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    cdk.Aspects.of(this).add(new AwsSolutionsChecks({ verbose: true }));

    const env = (this.node.tryGetContext("env") as string) ?? "dev";
    const isProd = env === "prod";

    // Apply required tags to all resources in the stack
    cdk.Tags.of(this).add("Project", "bedrock-converse-demo");
    cdk.Tags.of(this).add("Env", env);
    cdk.Tags.of(this).add("Owner", "gainsAI");

    // VPC — Lambda must be placed in a VPC to use Bedrock VPC endpoints
    const vpc = new ec2.Vpc(this, "Vpc", {
      maxAzs: 2,
      natGateways: isProd ? 2 : 1,
    });

    const logGroup = new logs.LogGroup(this, "ApiLogs", {
      retention: logs.RetentionDays.ONE_YEAR,
      removalPolicy: isProd ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY,
    });

    const fn = new lambda.Function(this, "ConverseFunction", {
      runtime: lambda.Runtime.PYTHON_3_13,
      architecture: lambda.Architecture.ARM_64,
      handler: "api.handler",
      code: lambda.Code.fromAsset("../backend/src"),
      vpc,
      tracing: lambda.Tracing.ACTIVE,
      reservedConcurrentExecutions: isProd ? 100 : 10,
      logGroup,
      environment: {
        LOG_LEVEL: isProd ? "WARNING" : "DEBUG",
      },
    });

    fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:InvokeModel"],
        resources: [
          `arn:aws:bedrock:${this.region}::foundation-model/anthropic.*`,
        ],
      })
    );

    // cloudwatch:PutMetricData does not support resource-level restrictions
    fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["cloudwatch:PutMetricData"],
        resources: ["*"],
      })
    );

    const api = new apigw.RestApi(this, "ConverseApi", {
      restApiName: `bedrock-converse-${env}`,
      deployOptions: {
        tracingEnabled: true,
        accessLogDestination: new apigw.LogGroupLogDestination(logGroup),
        accessLogFormat: apigw.AccessLogFormat.jsonWithStandardFields(),
      },
    });

    const integration = new apigw.LambdaIntegration(fn);
    api.root.addResource("converse").addMethod("POST", integration);
    api.root.addResource("health").addMethod("GET", integration);

    NagSuppressions.addResourceSuppressions(fn, [
      {
        id: "AwsSolutions-IAM5",
        reason:
          "cloudwatch:PutMetricData does not support resource-level restrictions per AWS docs",
      },
    ]);

    new cdk.CfnOutput(this, "ApiUrl", {
      value: api.url,
      description: "Bedrock Converse API URL",
    });
  }
}
