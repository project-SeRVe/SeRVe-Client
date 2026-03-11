"🚀 작업 공유: CLI 뼈대 구축 및 Auth / Repo 명령어 SDK 연동 완료"
이번 feature/repo-management 브랜치에서 터미널 CLI 도구의 뼈대를 잡고, 팀원이 개발한 serve_sdk와 명령어를 완벽하게 연동하는 작업을 완료했습니다. 백엔드 서버만 켜지면 바로 터미널에서 로그인과 저장소 관리가 가능합니다!

"1. 폴더 구조 개편 및 SDK 통합"

기존 최상단에 있던 serve_sdk를 새롭게 구성한 CLI 아키텍처(servis/) 안으로 이동 및 통합했습니다.

servis/cli (명령어 로직), servis/core (전역 설정), servis/serve_sdk (통신 엔진) 구조로 역할을 분리해 가독성과 확장성을 높였습니다.

"2. 계정 인증 (Auth) 명령어 구현"

servis login: 터미널 프롬프트로 이메일/비밀번호를 입력받아 SDK의 login() 함수를 호출합니다. 성공 시 ~/.servis/credentials.json에 자격 증명을 임시 저장하여 매번 로그인할 필요가 없게 만들었습니다.

servis logout: 로컬에 저장된 자격 증명을 안전하게 삭제합니다.

"3. 팀 저장소 관리 (Repo) 명령어 구현"

SDK의 팀/멤버 관리 API를 호출하는 명령어 껍데기를 만들고, Typer와 Rich 라이브러리를 사용해 결과를 예쁜 표(Table) 형태로 출력하도록 UI를 짰습니다.

연동 완료된 명령어: create(생성), list(목록 조회), show(상세 조회), invite(초대), kick(강퇴 및 키 로테이션 트리거), set-role(권한 변경)

"4. 실행 환경 및 설정 개선"

config.py: CLOUD_URL 환경 변수를 도입해서, 나중에 클라우드에 배포하더라도 코드 수정 없이 서버 주소를 바꿀 수 있도록 세팅했습니다.

pyproject.toml: 팀원들이 프로젝트 폴더에서 pip install -e .만 치면 전역에서 servis 명령어를 사용할 수 있게 패키징 설정을 맞췄습니다.

.gitignore에 가상환경(.venv) 찌꺼기가 깃허브에 올라가지 않도록 예외 처리를 추가했습니다.