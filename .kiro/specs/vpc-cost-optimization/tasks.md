# Implementation Plan: VPC Cost Optimization

## Overview

`lovv-dev-data-stack` CloudFormation 스택의 VPC Interface Endpoint 비용을 최적화한다. SSM VPC Endpoint를 단일 AZ로 CloudFormation 템플릿에 추가하고, Secrets Manager Endpoint가 이미 단일 AZ임을 확인하며, NAT 인스턴스 운영 가이드를 README에 추가한다. 테스트 코드로 변경 사항의 정합성을 검증한다.

## Tasks

- [x] 1. SSM VPC Endpoint를 CloudFormation 템플릿에 추가
  - [x] 1.1 `infra/data-stack/template.yaml`에 SSMVpcEndpoint 리소스 추가
    - `SecretsManagerVpcEndpoint` 리소스 바로 뒤, `DynamoDBGatewayEndpoint` 앞에 배치
    - Type: `AWS::EC2::VPCEndpoint`
    - Properties: VpcId `!Ref LovvDevVPC`, ServiceName `com.amazonaws.${AWS::Region}.ssm`, VpcEndpointType `Interface`, PrivateDnsEnabled `true`, SubnetIds `[!Ref LovvPrivateSubnetA]`, SecurityGroupIds `[!Ref LovvEndpointSecurityGroup]`
    - 한국어 주석 추가: "SSM Parameter Store VPC Endpoint: 현재 Lambda 런타임에서 미사용이나 향후 활용 가능성을 고려하여 단일 AZ로 유지한다."
    - _Requirements: 1.1, 1.2, 6.2, 6.4_

- [x] 2. SecretsManagerVpcEndpoint 단일 AZ 확인 및 RDS 보안 격리 검증
  - [x] 2.1 `infra/data-stack/template.yaml`에서 SecretsManagerVpcEndpoint의 SubnetIds가 `[!Ref LovvPrivateSubnetA]` 1개만 포함함을 확인
    - 현재 템플릿이 이미 올바른 상태이므로 변경 불필요
    - 변경이 필요한 경우에만 수정 (방어적 확인)
    - _Requirements: 2.1, 2.2_
  - [x] 2.2 RDS 보안 격리 구성이 유지됨을 확인
    - `LovvDBSubnetGroup` SubnetIds에 PrivateSubnetA + PrivateSubnetC 포함 확인
    - `LovvRDSInstance` PubliclyAccessible: false 확인
    - `LovvRDSSecurityGroup` 인바운드 규칙 변경 없음 확인
    - Private route table에 IGW 직접 라우트 없음 확인
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. NAT 인스턴스 운영 가이드를 README에 추가
  - [x] 3.1 `infra/data-stack/README.md`에 NAT 인스턴스 비용 최적화 운영 가이드 섹션 추가
    - DB 작업 시에만 NAT 인스턴스를 활성화하고 작업 완료 후 비활성화하도록 안내
    - AWS CLI를 이용한 수동 중지/시작 명령어 문서화 (`aws ec2 stop-instances`, `aws ec2 start-instances`)
    - Lambda가 NAT 인스턴스에 의존하지 않으며 VPC Endpoint로 모든 AWS 서비스에 접근함을 명시
    - 월 ~$3 절감 효과 안내
    - _Requirements: 7.2, 7.3, 7.4_

- [x] 4. Checkpoint - CloudFormation 템플릿 검증
  - Ensure `aws cloudformation validate-template --template-body file://infra/data-stack/template.yaml` 검증 통과, ask the user if questions arise.

- [x] 5. VPC Endpoint 테스트 코드 작성
  - [x] 5.1 `tests/test_data_stack_vpc_endpoints.py` 파일 생성 및 SSM Endpoint 단일 AZ 테스트 작성
    - 기존 `test_data_stack_nat_instance.py` 패턴을 따라 Python `unittest` 사용
    - `test_ssm_endpoint_single_az`: SSMVpcEndpoint SubnetIds에 `!Ref LovvPrivateSubnetA`만 포함 검증
    - `test_ssm_endpoint_private_dns_enabled`: PrivateDnsEnabled: true 검증
    - `test_ssm_endpoint_security_group`: SecurityGroupIds에 `!Ref LovvEndpointSecurityGroup` 포함 검증
    - _Requirements: 8.1, 1.1_
  - [x] 5.2 SecretsManager Endpoint 및 Gateway Endpoint 테스트 추가
    - `test_secretsmanager_endpoint_single_az`: SecretsManagerVpcEndpoint SubnetIds에 PrivateSubnetA만 포함 검증
    - `test_gateway_endpoints_unchanged`: DynamoDB/S3 Gateway Endpoint의 VpcId, ServiceName, VpcEndpointType, RouteTableIds 속성 무변경 검증
    - _Requirements: 8.2, 5.1, 5.2_
  - [x] 5.3 RDS 보안 격리 및 라우팅 테스트 추가
    - `test_rds_security_isolation`: RDS PubliclyAccessible=false, DBSubnetGroup에 양쪽 서브넷 포함 검증
    - `test_rds_security_group_rules`: RDS SG 인바운드 규칙이 DevMysqlIngressCidr과 조건부 NAT 인스턴스 규칙만 존재함을 검증
    - `test_private_route_no_igw`: Private route table에 IGW 직접 라우트 없음 검증
    - _Requirements: 8.3, 3.1, 3.2, 3.3, 3.4_
  - [x] 5.4 기존 `tests/test_data_stack_nat_instance.py` 업데이트
    - `test_existing_private_endpoint_and_rds_controls_remain`이 `SSMVpcEndpoint:` 존재를 이미 검증하므로 SSM 추가 후 통과 확인
    - SSMVpcEndpoint SubnetIds 수가 1개(PrivateSubnetA만)임을 검증하는 assertion이 있다면 단일 AZ로 변경
    - _Requirements: 8.4_

- [x] 6. Final checkpoint - 전체 테스트 실행
  - Ensure all tests pass (`python -m pytest tests/test_data_stack_vpc_endpoints.py tests/test_data_stack_nat_instance.py -v`), ask the user if questions arise.

## Notes

- 이 기능은 Infrastructure as Code(CloudFormation) 변경이므로 property-based testing은 적용하지 않는다
- 기존 `test_data_stack_nat_instance.py`의 `_block()` 헬퍼 패턴을 재사용하여 테스트 일관성을 유지한다
- Gateway Endpoint(S3, DynamoDB)는 무료이며 변경 대상이 아니다
- CloudFormation Import가 필요할 수 있음: 기존 콘솔에서 생성된 SSM Endpoint(`vpce-0acf51d81b0dfe1ec`)가 존재하므로 배포 시 충돌 가능성이 있다
- NAT 인스턴스 `EnableNatInstance` 기본값은 `false`로 유지되며, 운영 가이드만 추가한다
- Checkpoints에서 `aws cloudformation validate-template` 실행 시 `$env:AWS_CLI_FILE_ENCODING='UTF-8'` 설정 필요 (PowerShell 환경)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.1"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["5.1", "5.2", "5.3", "5.4"] }
  ]
}
```
