# S3 다운로드 설정 가이드

SeRVe-Client가 ALB 서버와 통신할 때 Task 데이터를 S3에서 직접 다운로드하는 방법을 안내합니다.

---

## 개요

### 서버 API 변경사항

ALB 서버는 Task 다운로드 시 암호화된 바이너리를 직접 반환하지 않고, S3 오브젝트 경로(`objectKey`)만 반환합니다.

**변경 전** (Mock 서버):
```json
{
  "id": 42,
  "content": "Base64 암호화된 바이너리...",
  "version": 1
}
```

**변경 후** (ALB 서버):
```json
{
  "id": 42,
  "objectKey": "team-id/task-id/task/filename",
  "version": 1
}
```

### S3 다운로드 방식

클라이언트는 `objectKey`를 받은 후, **boto3**를 사용해 S3에서 직접 암호화된 데이터를 다운로드합니다.

---

## 필수 요구사항

### 1. boto3 설치

```bash
cd /home/goldi1204/SeRVe-Client
source .venv/bin/activate
pip install boto3
```

### 2. AWS 자격증명 설정

S3에서 데이터를 다운로드하려면 AWS 자격증명이 필요합니다.

---

## AWS 자격증명 설정 방법

세 가지 방법 중 하나를 선택하세요.

### 방법 A: AWS CLI 설정 파일 (권장)

boto3가 자동으로 인식하는 표준 위치입니다.

```bash
# 1. 디렉토리 생성
mkdir -p ~/.aws

# 2. 자격증명 파일 생성
cat > ~/.aws/credentials << EOF
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
EOF

# 3. 권한 설정 (보안)
chmod 600 ~/.aws/credentials

# 4. 리전 설정 (선택)
cat > ~/.aws/config << EOF
[default]
region = ap-northeast-2
EOF
```

**장점**:
- boto3 표준 방식
- 여러 AWS 도구에서 공유 가능
- 프로필 관리 지원 (`[profile name]`)

### 방법 B: 환경변수

세션별로 자격증명을 설정합니다.

```bash
# 환경변수 설정
export AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY=YOUR_SECRET_ACCESS_KEY
export AWS_DEFAULT_REGION=ap-northeast-2

# 확인
echo $AWS_ACCESS_KEY_ID
```

**셸 재시작 시 유지**하려면 `~/.bashrc` 또는 `~/.zshrc`에 추가:

```bash
echo 'export AWS_ACCESS_KEY_ID=YOUR_KEY' >> ~/.bashrc
echo 'export AWS_SECRET_ACCESS_KEY=YOUR_SECRET' >> ~/.bashrc
echo 'export AWS_DEFAULT_REGION=ap-northeast-2' >> ~/.bashrc
source ~/.bashrc
```

**장점**:
- 간단한 설정
- CI/CD 환경에 적합

### 방법 C: .env 파일

SeRVe-Client의 `.env` 파일에 추가합니다.

```bash
cd /home/goldi1204/SeRVe-Client

# .env 파일에 추가
cat >> .env << EOF
AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_SECRET_ACCESS_KEY
AWS_DEFAULT_REGION=ap-northeast-2
EOF
```

그런 다음 `src/cli/context.py`에서 환경변수로 로드:

```python
# src/cli/context.py
import os
from dotenv import load_dotenv

load_dotenv()

# boto3가 자동으로 os.environ에서 읽음
```

**장점**:
- 프로젝트별 격리
- `.gitignore`로 안전하게 관리

---

## IAM 권한 요구사항

AWS 자격증명은 다음 권한이 필요합니다:

### 최소 권한 정책

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::servis-artifacts/*"
      ]
    }
  ]
}
```

### 필요 정보

- **버킷 이름**: `servis-artifacts`
- **리전**: `ap-northeast-2` (Seoul)
- **권한**: `s3:GetObject` (읽기 전용)

### IAM 사용자 생성 요청

인프라 담당자에게 다음 정보를 요청하세요:

1. **IAM 사용자 이름**: `serve-client-user` (예시)
2. **Access Key ID** 및 **Secret Access Key**
3. **정책**: 위 최소 권한 정책 적용
4. **버킷**: `servis-artifacts` 읽기 권한

---

## 동작 확인

### 1. 자격증명 테스트

Python에서 boto3 연결을 테스트합니다:

```python
import boto3

# S3 클라이언트 생성 (자격증명 자동 로드)
s3 = boto3.client('s3', region_name='ap-northeast-2')

# 버킷 목록 조회 (권한 확인)
try:
    response = s3.list_buckets()
    print("✓ AWS 자격증명 정상")
    print(f"버킷 목록: {[b['Name'] for b in response['Buckets']]}")
except Exception as e:
    print(f"✗ 자격증명 오류: {e}")
```

### 2. Task 다운로드 테스트

실제 Task를 다운로드해 봅니다:

```bash
cd /home/goldi1204/SeRVe-Client
source .venv/bin/activate

# 다운로드 실행
serve data download --output test.npz \
    1c221c1a-213c-4176-8db4-165154cad42f \
    3684
```

**예상 출력 (성공)**:
```
[+] Task 다운로드 중... (ID: 3684)
[+] S3에서 다운로드: 1c221c1a-213c-4176-8db4-165154cad42f/2aacac01-.../task/task1
[+] 복호화 중...
[+] 다운로드 완료: test.npz
```

**예상 출력 (실패 - 자격증명 없음)**:
```
[!] AWS 자격증명이 설정되지 않았습니다.
다음 중 하나를 설정하세요:
1. ~/.aws/credentials 파일
2. AWS_ACCESS_KEY_ID 환경변수
3. .env 파일에 AWS_* 추가

참고: docs/S3_DOWNLOAD.md
```

---

## 코드 내부 동작

### download_task() 플로우

```python
# serve_sdk/client.py
def download_task(self, team_id, task_id):
    # 1. 서버에서 Task 메타데이터 가져오기
    success, data = self.api.download_task(task_id, self.session.access_token)
    
    # 2. objectKey 확인
    object_key = data.get("objectKey")
    if object_key:
        # 3. S3에서 직접 다운로드 (boto3)
        success, encrypted_blob = self.api.download_from_s3(object_key)
    else:
        # Fallback: encryptedBlob 직접 반환 (구 버전 호환)
        encrypted_blob = data.get("encryptedBlob")
    
    # 4. 팀 키로 복호화
    team_key = self._ensure_team_key(team_id)
    decrypted_data = self.crypto.decrypt_data(encrypted_blob, team_key)
    
    return decrypted_data
```

### download_from_s3() 구현

```python
# serve_sdk/api_client.py
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

def download_from_s3(self, object_key: str, 
                     bucket_name: str = 'servis-artifacts',
                     region_name: str = 'ap-northeast-2') -> Tuple[bool, Optional[bytes]]:
    try:
        # boto3가 자동으로 자격증명을 찾음:
        # 1. 환경변수 (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        # 2. ~/.aws/credentials
        # 3. IAM Role (EC2 인스턴스)
        s3 = boto3.client('s3', region_name=region_name)
        
        # S3 객체 다운로드
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        data = response['Body'].read()
        
        return True, data
        
    except NoCredentialsError:
        return False, "AWS 자격증명이 설정되지 않았습니다. docs/S3_DOWNLOAD.md 참고"
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            return False, f"S3 객체를 찾을 수 없습니다: {object_key}"
        elif error_code == 'AccessDenied':
            return False, f"S3 접근 권한이 없습니다. IAM 정책 확인 필요"
        else:
            return False, f"S3 다운로드 오류: {e}"
```

---

## S3 ObjectKey 형식

서버가 반환하는 `objectKey` 형식입니다:

### Task 데이터

```
{teamId}/{taskId}/task/{fileName}
```

**예시**:
```
1c221c1a-213c-4176-8db4-165154cad42f/2aacac01-5c65-438f-9f58-ba58988125c6/task/task1
```

### VectorDemo 데이터

```
{teamId}/{taskId}/demo/demo_{demoIndex}.enc
```

**예시**:
```
1c221c1a-213c-4176-8db4-165154cad42f/2aacac01-5c65-438f-9f58-ba58988125c6/demo/demo_0.enc
```

### Artifact 데이터

```
{teamId}/{scenarioId}/{demoId}/{filename}
```

---

## 문제 해결

### 1. NoCredentialsError

**증상**:
```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**원인**: AWS 자격증명이 설정되지 않음

**해결**:
- 위의 "AWS 자격증명 설정 방법" 중 하나를 선택하여 설정
- 환경변수가 올바르게 로드되는지 확인:
  ```bash
  python -c "import os; print(os.getenv('AWS_ACCESS_KEY_ID'))"
  ```

### 2. AccessDenied

**증상**:
```
botocore.exceptions.ClientError: An error occurred (AccessDenied) when calling the GetObject operation
```

**원인**: IAM 사용자에게 S3 읽기 권한이 없음

**해결**:
- 인프라 담당자에게 `s3:GetObject` 권한 요청
- 버킷 정책 확인:
  ```bash
  aws s3api get-bucket-policy --bucket servis-artifacts
  ```

### 3. NoSuchKey

**증상**:
```
botocore.exceptions.ClientError: An error occurred (NoSuchKey) when calling the GetObject operation
```

**원인**: objectKey가 S3에 존재하지 않음

**해결**:
- 서버에서 반환한 objectKey 확인
- S3 콘솔 또는 CLI에서 객체 존재 여부 확인:
  ```bash
  aws s3 ls s3://servis-artifacts/{objectKey}
  ```

### 4. 자격증명이 여러 곳에 중복 설정됨

**증상**: 의도하지 않은 자격증명이 사용됨

**원인**: boto3는 다음 순서로 자격증명을 찾습니다:
1. 코드에서 명시적 전달 (`aws_access_key_id=...`)
2. 환경변수
3. `~/.aws/credentials`
4. IAM Role (EC2/ECS)

**해결**: 우선순위가 높은 설정을 제거하거나 원하는 자격증명으로 통일

---

## 대안: Presigned URL (미구현)

### 현재 상태

서버에 `/api/tasks/{id}/presigned-url` 엔드포인트가 존재하지만, **"미구현. 필요 시 추후 추가 예정"** 상태입니다.

### Presigned URL 방식의 장점

만약 서버에서 Presigned URL을 구현한다면:

1. **클라이언트가 boto3 불필요**
   - HTTP GET 요청만으로 다운로드 가능
   - AWS 자격증명 불필요

2. **서버가 접근 제어**
   - 서버가 임시 URL 생성 (유효기간 설정)
   - 권한 확인을 서버에서 처리

**서버 구현 예시**:
```java
// TaskController.java
@GetMapping("/api/tasks/{id}/presigned-url")
public ResponseEntity<Map<String, String>> getPresignedUrl(@PathVariable Long id) {
    String objectKey = taskService.getObjectKey(id);
    String presignedUrl = s3Service.generatePresignedUrl(objectKey, 3600); // 1시간
    return ResponseEntity.ok(Map.of("url", presignedUrl));
}
```

**클라이언트 사용 예시**:
```python
# boto3 없이 requests만 사용
response = requests.get(f"{API_URL}/api/tasks/{task_id}/presigned-url")
presigned_url = response.json()["url"]

# 일반 HTTP 다운로드
data = requests.get(presigned_url).content
```

### 요청 방법

서버 팀에게 Presigned URL 구현을 요청하려면:

1. **필요성 설명**: 클라이언트 AWS 자격증명 관리 부담 감소
2. **보안 고려**: URL 유효기간 설정 (예: 1시간)
3. **엔드포인트**: `GET /api/tasks/{id}/presigned-url` 구현
4. **응답 형식**:
   ```json
   {
     "url": "https://servis-artifacts.s3.ap-northeast-2.amazonaws.com/...",
     "expiresAt": "2026-03-10T13:00:00Z"
   }
   ```

---

## 참고 자료

### 관련 문서

- [서버 API 변경사항](/home/goldi1204/SeRVe-server/serve-core-client-변경사항.md)
- [boto3 공식 문서](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-example-download-file.html)
- [AWS 자격증명 설정](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)

### 서버 정보

- **ALB URL**: `http://k8s-servealb-a05f190fd7-1682512394.ap-northeast-2.elb.amazonaws.com`
- **S3 버킷**: `servis-artifacts`
- **리전**: `ap-northeast-2` (Seoul)

---

**Built with ❤️ for the Robotics Community**
