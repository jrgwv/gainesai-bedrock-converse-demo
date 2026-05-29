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

    cdk.Tags.of(this).add("Project", "bedrock-converse-demo");
    cdk.Tags.of(this).add("Env", env);
    cdk.Tags.of(this).add("Owner", "gainsAI");

    const vpcFlowLogGroup = new logs.LogGroup(this, "VpcFlowLogs", {
      retention: logs.RetentionDays.ONE_YEAR,
      removalPolicy: isProd ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY,
    });

    const vpc = new ec2.Vpc(this, "Vpc", {
      maxAzs: 2,
      natGateways: isProd ? 2 : 1,
      flowLogs: {
        ToCloudWatch: {
          destination: ec2.FlowLogDestination.toCloudWatchLogs(vpcFlowLogGroup),
          trafficType: ec2.FlowLogTrafficType.ALL,
        },
      },
    });

    const apiLogGroup = new logs.LogGroup(this, "ApiLogs", {
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
      logGroup: apiLogGroup,
      environment: {
        LOG_LEVEL: isProd ? "WARNING" : "DEBUG",
      },
    });

    // Model IDs are kept in sync with backend/src/config.py Settings defaults.
    // Cross-region inference profiles (us.*) require permission on both the
    // profile ARN and the underlying foundation-model ARNs the profile fans
    // out to in each region.
    const primaryModel = "anthropic.claude-opus-4-8";
    const fallbackModel = "anthropic.claude-haiku-4-5-20251001";

    fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:InvokeModel"],
        resources: [
          `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/us.${primaryModel}`,
          `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/us.${fallbackModel}`,
          `arn:aws:bedrock:*::foundation-model/${primaryModel}`,
          `arn:aws:bedrock:*::foundation-model/${fallbackModel}`,
        ],
      }),
    );

    // cloudwatch:PutMetricData does not support resource-level restrictions,
    // so we constrain it with a namespace condition instead — only metrics
    // under gainsAI/BedrockConverse can be published with this permission.
    fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["cloudwatch:PutMetricData"],
        resources: ["*"],
        conditions: {
          StringEquals: {
            "cloudwatch:namespace": "gainsAI/BedrockConverse",
          },
        },
      }),
    );

    const api = new apigw.RestApi(this, "ConverseApi", {
      restApiName: `bedrock-converse-${env}`,
      deployOptions: {
        tracingEnabled: true,
        loggingLevel: apigw.MethodLoggingLevel.INFO,
        dataTraceEnabled: false,
        metricsEnabled: true,
        accessLogDestination: new apigw.LogGroupLogDestination(apiLogGroup),
        accessLogFormat: apigw.AccessLogFormat.jsonWithStandardFields(),
      },
    });

    api.addRequestValidator("DefaultRequestValidator", {
      validateRequestBody: true,
      validateRequestParameters: true,
    });

    const integration = new apigw.LambdaIntegration(fn);
    api.root.addResource("converse").addMethod("POST", integration);
    api.root.addResource("health").addMethod("GET", integration);

    // ------------------------------------------------------------------
    // cdk-nag suppressions — each entry documents WHY the rule is waived.
    // ------------------------------------------------------------------

    // Lambda service role uses AWS-managed policies that are the canonical
    // grants for (a) writing CloudWatch logs and (b) managing the ENIs that
    // VPC-attached Lambdas need. Replacing these with customer-managed copies
    // would duplicate AWS-curated permissions with no security benefit.
    NagSuppressions.addResourceSuppressions(
      fn.role!,
      [
        {
          id: "AwsSolutions-IAM4",
          reason:
            "AWSLambdaBasicExecutionRole and AWSLambdaVPCAccessExecutionRole " +
            "are the AWS-recommended managed policies for Lambda log writes " +
            "and VPC ENI lifecycle; no customer-managed equivalent is needed.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
          ],
        },
        {
          id: "AwsSolutions-IAM5",
          reason:
            "bedrock:InvokeModel is enumerated to the two specific Claude " +
            "model IDs the application uses (Opus + Haiku from " +
            "backend/src/config.py). The region wildcard on the " +
            "foundation-model ARNs is required because cross-region " +
            "inference profiles (us.*) fan out to multiple regions at " +
            "runtime. cloudwatch:PutMetricData uses Resource '*' because " +
            "the action does not support resource ARNs, but is constrained " +
            "by a cloudwatch:namespace condition to the " +
            "gainsAI/BedrockConverse namespace only.",
          appliesTo: [
            "Resource::arn:aws:bedrock:*::foundation-model/anthropic.claude-opus-4-8",
            "Resource::arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001",
            "Resource::*",
          ],
        },
      ],
      true,
    );

    // API Gateway's CloudWatch role uses the AWS-managed
    // AmazonAPIGatewayPushToCloudWatchLogs policy — this is the only policy
    // the API Gateway service principal accepts for access-log delivery.
    NagSuppressions.addResourceSuppressionsByPath(
      this,
      `/${this.stackName}/ConverseApi/CloudWatchRole/Resource`,
      [
        {
          id: "AwsSolutions-IAM4",
          reason:
            "AmazonAPIGatewayPushToCloudWatchLogs is the AWS-mandated " +
            "managed policy for the API Gateway account-level CloudWatch role.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs",
          ],
        },
      ],
    );

    // Python 3.13 is the latest Lambda runtime available; cdk-nag's runtime
    // catalogue can lag behind AWS announcements.
    NagSuppressions.addResourceSuppressions(fn, [
      {
        id: "AwsSolutions-L1",
        reason:
          "Lambda is already pinned to Python 3.13, the latest available runtime.",
      },
    ]);

    // WAF and authentication are deferred to the deployment layer for this
    // demo. Production deployments are expected to front the API with WAFv2
    // and an authorizer (Cognito or custom). Documented here so the next
    // operator knows the gap is intentional, not an oversight.
    NagSuppressions.addResourceSuppressions(
      api,
      [
        {
          id: "AwsSolutions-APIG3",
          reason:
            "WAFv2 association is handled at the deployment layer outside " +
            "this stack; demo environments do not provision a web ACL.",
        },
        {
          id: "AwsSolutions-APIG4",
          reason:
            "Demo endpoints are intentionally unauthenticated. Production " +
            "deployments add a Cognito or Lambda authorizer at the route level.",
        },
        {
          id: "AwsSolutions-COG4",
          reason:
            "Cognito user pool integration is out of scope for the demo; " +
            "see AwsSolutions-APIG4 suppression for the production plan.",
        },
      ],
      true,
    );

    new cdk.CfnOutput(this, "ApiUrl", {
      value: api.url,
      description: "Bedrock Converse API URL",
    });
  }
}
