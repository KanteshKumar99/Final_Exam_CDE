import aws_cdk as cdk
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_iam as iam
from aws_cdk import aws_msk as msk
from constructs import Construct

class ConnectStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, msk_cluster_arn: str, msk_sg_id: str, vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. S3 Bucket for Backup & Connect Plugins
        self.backup_bucket = s3.Bucket(
            self, "IotBackupBucket",
            bucket_name=f"iot-events-backup-{cdk.Aws.ACCOUNT_ID}",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True
        )

        # 2. IAM Role for MSK Connect Service Execution
        self.connect_role = iam.Role(
            self, "MskConnectRole",
            assumed_by=iam.ServicePrincipal("kafkaconnect.amazonaws.com"),
            description="IAM Role for MSK Connect connectors to access S3, Secrets Manager, and MSK"
        )

        # Grant S3 read/write access
        self.backup_bucket.grant_read_write(self.connect_role)

        # Basic MSK actions
        self.connect_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kafka:DescribeCluster",
                    "kafka:GetBootstrapBrokers",
                    "kafka-cluster:Connect",
                    "kafka-cluster:DescribeCluster",
                    "kafka-cluster:CreateTopic",
                    "kafka-cluster:DescribeTopic",
                    "kafka-cluster:ReadData",
                    "kafka-cluster:WriteData",
                    "kafka-cluster:DescribeGroup",
                    "kafka-cluster:AlterGroup"
                ],
                resources=["*"]
            )
        )

        # Allow secrets decryption for db password
        self.connect_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=["*"]
            )
        )

        # Outputs
        cdk.CfnOutput(
            self, "BackupBucketName",
            value=self.backup_bucket.bucket_name,
            description="Name of the S3 backup bucket"
        )
        cdk.CfnOutput(
            self, "MskConnectRoleArn",
            value=self.connect_role.role_arn,
            description="ARN of the MSK Connect service execution role"
        )
