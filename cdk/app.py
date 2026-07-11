#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.vpc_stack import VpcStack
from stacks.msk_stack import MskStack
from stacks.ec2_db_stack import Ec2DbStack
from stacks.connect_stack import ConnectStack

app = cdk.App()

# Create target environment configuration
env = cdk.Environment(
    account=cdk.Aws.ACCOUNT_ID,
    region=cdk.Aws.REGION
)

# 1. VPC Stack
vpc_stack = VpcStack(
    app, "IoT-VpcStack",
    env=env,
    description="Network VPC structure for IoT Ingestion Hackathon"
)

# 2. MSK Kafka Stack
msk_stack = MskStack(
    app, "IoT-MskStack",
    vpc=vpc_stack.vpc,
    env=env,
    description="AWS MSK Kafka Cluster for streaming IoT data"
)
msk_stack.add_dependency(vpc_stack)

# 3. PostgreSQL Database Stack (On-Prem Simulation)
ec2_db_stack = Ec2DbStack(
    app, "IoT-Ec2DbStack",
    vpc=vpc_stack.vpc,
    env=env,
    description="Private EC2 instance running PostgreSQL + Bastion host"
)
ec2_db_stack.add_dependency(vpc_stack)

# 4. MSK Connect & S3 Stack
connect_stack = ConnectStack(
    app, "IoT-ConnectStack",
    msk_cluster_arn=msk_stack.msk_cluster.ref,
    msk_sg_id=msk_stack.msk_sg.security_group_id,
    vpc=vpc_stack.vpc,
    env=env,
    description="MSK Connect infrastructure and S3 backup bucket"
)
connect_stack.add_dependency(msk_stack)
connect_stack.add_dependency(ec2_db_stack)

app.synth()
