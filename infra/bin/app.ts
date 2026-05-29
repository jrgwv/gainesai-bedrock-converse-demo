#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { BedrockStack } from "../lib/bedrock-stack";

const app = new cdk.App();

const env = (app.node.tryGetContext("env") as string) ?? "dev";

new BedrockStack(app, `BedrockConverse-${env}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
  },
  tags: {
    Project: "bedrock-converse-demo",
    Env: env,
    Owner: "gainsai",
  },
});
