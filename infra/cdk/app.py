#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.presales_stack import PresalesStack

app = cdk.App()

env_name = app.node.try_get_context("env") or "production"

PresalesStack(
    app, f"AiPresalesStack-{env_name}",
    env_name=env_name,
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "me-central-1"),
    ),
    description="AI Presales Assistant SaaS — backend, frontend, RDS, Redis, S3 (ECS Fargate)",
)

app.synth()
