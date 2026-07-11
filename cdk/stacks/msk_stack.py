import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_msk as msk
from constructs import Construct

class MskStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Security Group for MSK brokers
        self.msk_sg = ec2.SecurityGroup(
            self, "MskSecurityGroup",
            vpc=vpc,
            description="Security group for MSK Kafka brokers",
            allow_all_outbound=True
        )

        # Allow ingress from within the VPC on MSK ports: 9092 (plaintext) and 9094 (TLS)
        self.msk_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(9092),
            description="Allow plaintext MSK traffic from VPC"
        )
        self.msk_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(9094),
            description="Allow TLS MSK traffic from VPC"
        )

        # Extract private subnet IDs
        private_subnets = [subnet.subnet_id for subnet in vpc.private_subnets]

        # Define MSK Cluster using L1 Construct (CfnCluster) for maximum stability
        self.msk_cluster = msk.CfnCluster(
            self, "IoT-MskCluster",
            cluster_name="iot-events-cluster",
            kafka_version="3.4.0",
            number_of_broker_nodes=3,
            broker_node_group_info=msk.CfnCluster.BrokerNodeGroupInfoProperty(
                instance_type="kafka.t3.small",
                client_subnets=private_subnets,
                security_groups=[self.msk_sg.security_group_id],
                storage_info=msk.CfnCluster.StorageInfoProperty(
                    ebs_storage_info=msk.CfnCluster.EBSStorageInfoProperty(
                        volume_size=10
                    )
                )
            ),
            encryption_info=msk.CfnCluster.EncryptionInfoProperty(
                encryption_in_transit=msk.CfnCluster.EncryptionInTransitProperty(
                    client_broker="TLS_PLAINTEXT",
                    in_cluster=True
                )
            )
        )

        # Outputs
        cdk.CfnOutput(
            self, "MskClusterName",
            value=self.msk_cluster.cluster_name,
            description="Name of the MSK Cluster"
        )
        cdk.CfnOutput(
            self, "MskSecurityGroupId",
            value=self.msk_sg.security_group_id,
            description="MSK Security Group ID"
        )
