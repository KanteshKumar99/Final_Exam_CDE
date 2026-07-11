import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

class VpcStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create VPC with Public and Private subnets across 3 AZs
        self.vpc = ec2.Vpc(
            self, "IoT-Vpc",
            max_azs=3,
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ]
        )

        # Output the VPC ID
        cdk.CfnOutput(
            self, "VpcId",
            value=self.vpc.vpc_id,
            description="VPC ID of the IoT ingestion network",
            export_name="IoT-VpcId"
        )
