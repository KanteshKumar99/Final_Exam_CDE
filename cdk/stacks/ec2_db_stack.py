import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

class Ec2DbStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. PostgreSQL Credentials in Secrets Manager
        self.db_secret = secretsmanager.Secret(
            self, "PostgreSqlCredentials",
            secret_name="iot-postgresql-credentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "postgres"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=16
            )
        )

        # 2. Security Group for PostgreSQL EC2
        self.db_sg = ec2.SecurityGroup(
            self, "PostgresSecurityGroup",
            vpc=vpc,
            description="Security group for private PostgreSQL EC2 instance",
            allow_all_outbound=True
        )
        
        # Allow Postgres traffic from within VPC
        self.db_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL connections from VPC"
        )

        # 3. Security Group for Bastion Host
        self.bastion_sg = ec2.SecurityGroup(
            self, "BastionSecurityGroup",
            vpc=vpc,
            description="Security group for public Bastion Host",
            allow_all_outbound=True
        )

        # 4. IAM Role for Systems Manager (SSM) access
        ssm_role = iam.Role(
            self, "Ec2SsmRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ]
        )
        self.db_secret.grant_read(ssm_role)

        # 5. Launch PostgreSQL EC2 in Private Subnet
        # Amazon Linux 2023
        ami = ec2.MachineImage.latest_amazon_linux2023()

        self.db_instance = ec2.Instance(
            self, "PostgresEc2",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machine_image=ami,
            security_group=self.db_sg,
            role=ssm_role,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(15) # 15GB disk
                )
            ]
        )

        # UserData for EC2 to setup PostgreSQL & logical replication
        # Fetching password from Secrets Manager at boot
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "dnf update -y",
            "dnf install -y postgresql15-server postgresql15 jq",
            "postgresql-setup --initdb",
            # Enable logical replication
            "sed -i \"s/#wal_level = replica/wal_level = logical/\" /var/lib/pgsql/data/postgresql.conf",
            "sed -i \"s/#max_replication_slots = 10/max_replication_slots = 4/\" /var/lib/pgsql/data/postgresql.conf",
            "sed -i \"s/#max_wal_senders = 10/max_wal_senders = 4/\" /var/lib/pgsql/data/postgresql.conf",
            # Listen on all addresses
            "echo \"listen_addresses = '*'\" >> /var/lib/pgsql/data/postgresql.conf",
            # Allow access from VPC
            f"echo \"host all all {vpc.vpc_cidr_block} md5\" >> /var/lib/pgsql/data/pg_hba.conf",
            f"echo \"host replication all {vpc.vpc_cidr_block} md5\" >> /var/lib/pgsql/data/pg_hba.conf",
            # Start service
            "systemctl start postgresql",
            "systemctl enable postgresql",
            # Fetch secret password and create roles/db/tables
            f"SECRET_VAL=$(aws secretsmanager get-secret-value --secret-id {self.db_secret.secret_arn} --region {self.region} --query SecretString --output text)",
            "DB_PASS=$(echo $SECRET_VAL | jq -r .password)",
            # Setup DB & Tables
            "sudo -u postgres psql -c \"ALTER USER postgres WITH PASSWORD '$DB_PASS';\"",
            "sudo -u postgres psql -c \"CREATE DATABASE iot_db;\"",
            # Create user for CDC and replication
            "sudo -u postgres psql -d iot_db -c \"CREATE USER replication_user WITH REPLICATION PASSWORD '$DB_PASS';\"",
            # Create iot_events table
            "sudo -u postgres psql -d iot_db -c \""
            "CREATE TABLE IF NOT EXISTS public.iot_events ("
            "  id SERIAL PRIMARY KEY,"
            "  device_id VARCHAR(50) NOT NULL,"
            "  latitude DOUBLE PRECISION NOT NULL,"
            "  longitude DOUBLE PRECISION NOT NULL,"
            "  aqi INT,"
            "  temperature NUMERIC(5,2),"
            "  timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
            ");\"",
            "sudo -u postgres psql -d iot_db -c \"GRANT ALL PRIVILEGES ON TABLE public.iot_events TO replication_user;\"",
            "sudo -u postgres psql -d iot_db -c \"GRANT USAGE, SELECT ON SEQUENCE iot_events_id_seq TO replication_user;\""
        )
        self.db_instance.add_user_data(*user_data.render().split('\n'))

        # 6. Launch Bastion Host in Public Subnet
        self.bastion_instance = ec2.Instance(
            self, "BastionEc2",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machine_image=ami,
            security_group=self.bastion_sg,
            role=ssm_role
        )

        # UserData for Bastion to install postgresql client
        bastion_user_data = ec2.UserData.for_linux()
        bastion_user_data.add_commands(
            "dnf update -y",
            "dnf install -y postgresql15 jq"
        )
        self.bastion_instance.add_user_data(*bastion_user_data.render().split('\n'))

        # Outputs
        cdk.CfnOutput(
            self, "PostgresPrivateIp",
            value=self.db_instance.instance_private_ip,
            description="Private IP of the PostgreSQL EC2 instance"
        )
        cdk.CfnOutput(
            self, "SecretsManagerArn",
            value=self.db_secret.secret_arn,
            description="ARN of PostgreSQL credentials in Secrets Manager"
        )
        cdk.CfnOutput(
            self, "BastionInstanceId",
            value=self.bastion_instance.instance_id,
            description="Instance ID of the Bastion Host"
        )
