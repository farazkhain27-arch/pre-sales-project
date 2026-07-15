"""
AI Presales Assistant — production AWS stack.

Topology:
  Internet -> ALB -> ECS Fargate (frontend: nginx serving React build)
                   -> ALB -> ECS Fargate (backend: FastAPI)  [/api/* path routing]
  backend  -> RDS PostgreSQL (private subnet)
  backend  -> ElastiCache Redis (private subnet)
  backend  -> S3 bucket (uploaded RFPs/BOQs/datasheets, extracted documents)
  secrets  -> Secrets Manager (DB credentials, JWT secret, Anthropic API key)

Same pattern used for the NOC Agentic AI Platform / Medical Triage / WebSentry
deployments: ECS Fargate + CDK, so ops runbooks stay consistent across projects.
"""
from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr_assets as ecr_assets,
    aws_rds as rds,
    aws_elasticache as elasticache,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
)
from constructs import Construct


class PresalesStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, env_name: str = "production", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # Networking
        # ---------------------------------------------------------------
        vpc = ec2.Vpc(
            self, "PresalesVpc",
            max_azs=2,
            nat_gateways=1,   # one NAT for cost control; use 2 for HA in real prod
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
                ec2.SubnetConfiguration(name="isolated", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24),
            ],
        )

        cluster = ecs.Cluster(self, "PresalesCluster", vpc=vpc, container_insights=True)

        # ---------------------------------------------------------------
        # Secrets
        # ---------------------------------------------------------------
        db_credentials = rds.Credentials.from_generated_secret("presales_admin")

        app_secrets = secretsmanager.Secret(
            self, "AppSecrets",
            secret_name=f"ai-presales/{env_name}/app-secrets",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"ANTHROPIC_API_KEY":""}',
                generate_string_key="JWT_SECRET",
                exclude_punctuation=True,
                password_length=48,
            ),
        )

        # ---------------------------------------------------------------
        # Storage — RFPs, BOQs, datasheets, generated proposals
        # ---------------------------------------------------------------
        documents_bucket = s3.Bucket(
            self, "DocumentsBucket",
            bucket_name=f"ai-presales-documents-{env_name}-{self.account}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[s3.LifecycleRule(
                id="transition-old-versions",
                noncurrent_version_transitions=[s3.NoncurrentVersionTransition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(90),
                )],
            )],
        )

        # ---------------------------------------------------------------
        # Database — PostgreSQL (Multi-AZ optional for prod)
        # ---------------------------------------------------------------
        db_instance = rds.DatabaseInstance(
            self, "PresalesDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16_3),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.SMALL),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            credentials=db_credentials,
            database_name="presales",
            allocated_storage=50,
            max_allocated_storage=200,
            multi_az=(env_name == "production"),
            backup_retention=Duration.days(7),
            removal_policy=RemovalPolicy.SNAPSHOT,
            deletion_protection=(env_name == "production"),
        )

        # ---------------------------------------------------------------
        # Redis — session/job cache
        # ---------------------------------------------------------------
        redis_subnet_group = elasticache.CfnSubnetGroup(
            self, "RedisSubnetGroup",
            description="Private subnets for Redis",
            subnet_ids=vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED).subnet_ids,
        )
        redis_sg = ec2.SecurityGroup(self, "RedisSG", vpc=vpc, allow_all_outbound=True)
        redis_cluster = elasticache.CfnCacheCluster(
            self, "PresalesRedis",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1,
            cache_subnet_group_name=redis_subnet_group.ref,
            vpc_security_group_ids=[redis_sg.security_group_id],
        )

        # ---------------------------------------------------------------
        # Backend service — FastAPI on Fargate behind an internal ALB path
        # ---------------------------------------------------------------
        backend_image = ecr_assets.DockerImageAsset(
            self, "BackendImage", directory="../../backend",
        )

        backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "BackendService",
            cluster=cluster,
            cpu=512,
            memory_limit_mib=1024,
            desired_count=2,
            public_load_balancer=True,
            listener_port=80,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(backend_image),
                container_port=8000,
                environment={
                    "ENV": env_name,
                    "DEBUG": "false",
                    "AWS_REGION": self.region,
                    "S3_BUCKET": documents_bucket.bucket_name,
                    "USE_S3": "true",
                    "DB_HOST": db_instance.db_instance_endpoint_address,
                    "DB_PORT": "5432",
                    "DB_NAME": "presales",
                    "DB_USER": "presales_admin",
                },
                secrets={
                    "JWT_SECRET": ecs.Secret.from_secrets_manager(app_secrets, "JWT_SECRET"),
                    "ANTHROPIC_API_KEY": ecs.Secret.from_secrets_manager(app_secrets, "ANTHROPIC_API_KEY"),
                    "DB_PASSWORD": ecs.Secret.from_secrets_manager(db_instance.secret, "password"),
                },
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="presales-backend", log_retention=logs.RetentionDays.TWO_WEEKS),
            ),
        )
        backend_service.target_group.configure_health_check(path="/health", healthy_http_codes="200")
        backend_service.service.connections.allow_to(db_instance, ec2.Port.tcp(5432), "backend to RDS")
        backend_service.service.connections.allow_to(redis_sg, ec2.Port.tcp(6379), "backend to Redis")
        documents_bucket.grant_read_write(backend_service.task_definition.task_role)

        # ---------------------------------------------------------------
        # Frontend service — nginx serving the React build
        # ---------------------------------------------------------------
        frontend_image = ecr_assets.DockerImageAsset(
            self, "FrontendImage", directory="../../frontend",
        )

        frontend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "FrontendService",
            cluster=cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=2,
            public_load_balancer=True,
            listener_port=80,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(frontend_image),
                container_port=80,
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="presales-frontend", log_retention=logs.RetentionDays.TWO_WEEKS),
            ),
        )
        frontend_service.target_group.configure_health_check(path="/", healthy_http_codes="200")

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        CfnOutput(self, "FrontendURL", value=f"http://{frontend_service.load_balancer.load_balancer_dns_name}")
        CfnOutput(self, "BackendURL", value=f"http://{backend_service.load_balancer.load_balancer_dns_name}")
        CfnOutput(self, "DatabaseEndpoint", value=db_instance.db_instance_endpoint_address)
        CfnOutput(self, "DocumentsBucketName", value=documents_bucket.bucket_name)
