# Lovv Data Stack

Stateful data-stack artifacts for Lovv backend. These resources are intentionally kept outside the AWS SAM application stack.

## Files

```text
infra/data-stack/template.yaml
infra/data-stack/parameters/dev.parameters.example.json
infra/data-stack/rds/schema.sql
infra/data-stack/rds/reference_queries.sql
```

Related schema contracts:

```text
docs/SPEC/db_build_spec.md
docs/SPEC/service_api_schema_extension_spec.md
docs/PLAN/service_api_schema_extension_plan.md
```

주석 정책:

- CloudFormation YAML과 SQL 파일에는 한국어 주석을 함께 둔다.
- JSON parameter example은 JSON 표준상 주석을 넣을 수 없으므로, 설명은 이 README와 `reports/` 문서에 둔다.

## Development defaults

Development is standardized as:

- Stack: `lovv-dev-data-stack`
- Environment: `dev`
- Database: `lovvdev`
- DynamoDB prefix: `lovv_dev_`
- SSM prefix: `/lovv/dev/`
- Image CDN: CloudFront distribution with OAC read-only access to the private image bucket.

Use `infra/data-stack/parameters/dev.parameters.example.json` as the single development parameter source. Replace placeholder subnet and security group IDs with actual development VPC values before deployment.
The template now creates the development VPC, two private subnets, and RDS security group directly, so separate subnet or security group IDs are not required for the default dev deployment.
The template also creates VPC Endpoints for Secrets Manager, SSM, DynamoDB, and S3 so SAM Lambda functions in the private subnets can reach required AWS services without a NAT Gateway.
The template creates a read-only CloudFront distribution for the image bucket. Frontend code must use the CloudFront base URL from `/lovv/dev/cloudfront/image_base_url`, not the direct S3 bucket URL.

## Optional NAT instance

The Data Stack can create a dev-only NAT instance when private-subnet workloads need outbound public internet access beyond the AWS services already covered by VPC Endpoints.

Default behavior:

- `EnableNatInstance=false`
- No public subnet, Internet Gateway, NAT EC2 instance, or private default route is created.
- S3, DynamoDB, SSM, and Secrets Manager access continues to use VPC Endpoints.

Validate the template before deployment:

```powershell
$env:AWS_CLI_FILE_ENCODING='UTF-8'; aws cloudformation validate-template --template-body file://infra/data-stack/template.yaml
```

Enable only for a development stack that needs public egress. Before enabling, set `EnableNatInstance` to `true` in the deployment parameter overrides. This starts an EC2 instance and may create public internet data-transfer cost. Deployments that create the NAT instance IAM role require `CAPABILITY_IAM`.

Operational notes:

- The NAT instance is single-AZ and intended for dev only.
- SSH ingress is not opened. Use AWS Systems Manager Session Manager if shell access is required.
- The NAT instance role grants SSM management only and should not receive RDS, DynamoDB, S3 data-plane, or Secrets Manager data permissions.
- When NAT is enabled, the RDS security group allows MySQL only from the NAT instance security group. RDS remains private and `PubliclyAccessible=false`.
- Production public egress needs a separate HA design review, likely NAT Gateway or multi-AZ NAT routing.

### NAT 인스턴스 비용 최적화 운영 가이드

NAT 인스턴스(t4g.nano, `i-0c6dad9690abd0101`)는 개발자가 SSM port forwarding으로 private RDS에 접속할 때만 필요하다. Lambda 함수는 VPC Endpoint(Secrets Manager, DynamoDB Gateway, S3 Gateway)를 통해 모든 AWS 서비스에 접근하므로 NAT 인스턴스에 의존하지 않는다. NAT 인스턴스가 stopped 상태여도 Lambda의 정상 동작에는 영향이 없다.

DB 작업 시에만 NAT 인스턴스를 시작하고, 작업 완료 후 즉시 중지하면 월 ~$3(t4g.nano running 비용)을 절감할 수 있다.

#### NAT 인스턴스 시작 (DB 작업 전)

```powershell
# NAT 인스턴스 ID 조회
$natInstanceId = aws ssm get-parameter --name /lovv/dev/network/nat_instance_id --query Parameter.Value --output text

# NAT 인스턴스 시작
aws ec2 start-instances --instance-ids $natInstanceId

# running 상태 대기
aws ec2 wait instance-running --instance-ids $natInstanceId
```

#### NAT 인스턴스 중지 (DB 작업 완료 후)

```powershell
# NAT 인스턴스 중지
aws ec2 stop-instances --instance-ids $natInstanceId

# stopped 상태 대기
aws ec2 wait instance-stopped --instance-ids $natInstanceId
```

#### 운영 주의사항

- NAT 인스턴스를 중지해도 VPC Lambda(Auth, Admin, SavedPlans, Preference)는 VPC Endpoint를 통해 Secrets Manager, DynamoDB, S3, SSM Parameter Store에 정상 접근한다.
- CloudFormation `EnableNatInstance` 기본값은 `false`이다. 신규 배포 시 NAT 인스턴스는 생성되지 않는다.
- NAT 인스턴스가 필요한 시나리오: SSM port forwarding을 통한 로컬 MySQL 클라이언트의 private RDS 접속.
- 장시간 유휴 상태로 방치하지 않도록 작업 후 반드시 중지한다.

### RDS access through SSM port forwarding

Use the NAT instance as an SSM-managed access host, not as a public MySQL endpoint.

1. Read the deployed values:

```powershell
$natInstanceId = aws ssm get-parameter --name /lovv/dev/network/nat_instance_id --query Parameter.Value --output text
$rdsHost = aws ssm get-parameter --name /lovv/dev/rds/host --query Parameter.Value --output text
```

2. Start local port forwarding through the NAT instance to private RDS:

```powershell
aws ssm start-session --target $natInstanceId --document-name AWS-StartPortForwardingSessionToRemoteHost --parameters "host=$rdsHost,portNumber=3306,localPortNumber=3306"
```

3. Connect from a local MySQL client while the session is open:

```powershell
mysql -h 127.0.0.1 -P 3306 -u lovvadmin -p
```

## Report

Detailed deployment, validation, and operation notes have been moved to:

```text
reports/data_stack_build_report.md
```

SAM developers and agents should read the report section `SAM Integration Notes` before adding Lambda `VpcConfig`, database environment variables, Secrets Manager permissions, DynamoDB permissions, or S3 image-bucket permissions.

For VPC access patterns, read the report section `VPC Connection Guide`.

For frontend image delivery, read the report section `Image CDN Frontend Handoff`. The CloudFront endpoint allows only `GET` and `HEAD`, and its S3 bucket policy grants only `s3:GetObject` through OAC.
Frontend handoff summary: `reports/image_cdn_frontend_handoff_20260615_ko.md`

For Auth, Preference, Saved Plans, and Reaction APIs, read `docs/SPEC/service_api_schema_extension_spec.md` before changing RDS tables, DynamoDB auth sessions, or service reference queries.
