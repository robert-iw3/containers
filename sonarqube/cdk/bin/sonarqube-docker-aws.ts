#!/usr/bin/env node
import * as cdk from "@aws-cdk/core";
import { SonarqubeDockerAwsStack } from "../lib/sonarqube-docker-aws-stack";

const app = new cdk.App();
const stackProps = {
  env: {
    region: process.env.REGION,
    account: process.env.ACCOUNT_ID,
  },
};

new SonarqubeDockerAwsStack(app, "SonarqubeDockerAwsStack", stackProps);
