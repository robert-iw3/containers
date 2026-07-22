import * as cdk from 'aws-cdk-lib';
//import ec2 from 'aws-cdk-lib/aws-ec2';
import ecs from 'aws-cdk-lib/aws-ecs';
import ecs_patterns from 'aws-cdk-lib/aws-ecs-patterns';
import { DockerImageAsset } from 'aws-cdk-lib/aws-ecr-assets';
import { join } from 'path';
import { aws_ec2 as ec2 } from 'aws-cdk-lib';

export class SonarqubeDockerAwsStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const image = new DockerImageAsset(this, "BackendImage", {
      directory: join(__dirname, "..", "service"),
    });

    //const privateSubnet = new ec2.PrivateSubnet(this, 'SonarqubePrivateSubnet', {
    //  availabilityZone: 'us-west-2a',
    //  cidrBlock: '10.0.0.77/24',
    //  vpcId: '<vpcId after creating it',

      // the properties below are optional
    //  mapPublicIpOnLaunch: false,
    //});
    //new PrivateSubnet(scope: Construct, id: string, props: PrivateSubnetProps)

    // At least 2 AZ required
    const vpc = new ec2.Vpc(this, "SonarqubeVpc", {
      ipAddresses: ec2.IpAddresses.cidr(this.props.vpcCidr),
      enableDnsHostnames: true,
      enableDnsSupport: true,
      maxAzs: this.props.availabilityZones.length,
      subnetConfiguration: [
        {
          name: "sonarqube-services",
          cidrMask: 28,
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
        {
          name: "transit-gateway",
          cidrMask: 28,
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
      ],
    });

    this.tgw = new ec2.CfnTransitGateway(this, "TransitGateway", {
      amazonSideAsn: props.amazonSideAsn ? props.amazonSideAsn : 65521,
      autoAcceptSharedAttachments: "enable",
      defaultRouteTableAssociation: "disable",
      defaultRouteTablePropagation: "disable",
      vpnEcmpSupport: "enable",
      description: props.tgwDescription,
      tags: [
        {
          key: "SonarqubeGateway",
          value: this.name,
        },
      ],
    });

    this.vpc = new ec2.Vpc(this, this.name, {
      ipAddresses: ec2.IpAddresses.cidr(this.props.vpcCidr),
      enableDnsHostnames: true,
      enableDnsSupport: true,
      maxAzs: this.props.availabilityZones.length,
      subnetConfiguration: [
        {
          name: "nat-egress",
          cidrMask: 28,
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          name: "transit-gateway",
          cidrMask: 28,
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });
    this.publicSubnetNames.push("nat-egress");
    // We're NATing our transit gateway connections, so we consider it a 'private' in this use-case.
    this.privateSubnetNames.push("transit-gateway");

    const cluster = new ecs.Cluster(this, "Cluster", {
      vpc,
    });

    // Create a load-balanced Fargate service
    new ecs_patterns.ApplicationLoadBalancedFargateService(
      this,
      "SonarqubeFargateService",
      {
        cluster: cluster,
        cpu: 1024,
        desiredCount: 4,
        taskImageOptions: {
          image: ecs.ContainerImage.fromDockerImageAsset(image),
          containerPort: 9000,
        },
        memoryLimitMiB: 8192,
        publicLoadBalancer: false,
        healthCheckGracePeriod: 30,
        domainName: sonarqube.dev.io,
        listenerPort: http,
        serviceName: sonarqube,
      }
    );
  }
}
