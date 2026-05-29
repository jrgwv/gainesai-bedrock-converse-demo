import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";

export class PipelineStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    // TODO: Add GitHub Actions OIDC role for CDK deploy or CodePipeline
  }
}
