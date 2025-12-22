"""
Session Manager - Zero-Trust 메모리 상태 관리

서버가 알아서는 안 되는 민감 정보를 프로그램 실행 중에만 메모리에 보관:
- 복호화된 개인키 (서버는 암호화된 버전만 알고 있음)
- 현재 작업 중인 저장소의 원본 팀 키 (서버는 래핑된 버전만 알고 있음)
- JWT 액세스 토큰

프로그램 재시작 시 모든 데이터가 사라지므로, 필요할 때마다 서버에서
암호화된 값을 받아와 복호화하는 lazy loading 패턴을 사용한다.
"""

from typing import Optional, Dict


class Session:
    """
    Zero-Trust 아키텍처를 위한 클라이언트 측 메모리 저장소

    Singleton 패턴으로 구현하여 앱 전체에서 단일 인스턴스 사용
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Session, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """세션 초기화"""
        self.access_token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.email: Optional[str] = None

        # 복호화된 내 개인키 (KeysetHandle 객체)
        # 로그인 시 서버의 encryptedPrivateKey를 비밀번호로 복호화하여 저장
        self.private_key_handle = None

        # 복호화된 내 공개키 (KeysetHandle 객체)
        # 개인키에서 파생 가능
        self.public_key_handle = None

        # 현재 작업 중인 저장소들의 팀 키 캐시
        # {repo_id: aes_keyset_handle} 형태
        self.team_keys: Dict[int, any] = {}

    def is_authenticated(self) -> bool:
        """로그인 상태 확인"""
        return self.access_token is not None and self.user_id is not None

    def has_private_key(self) -> bool:
        """개인키가 복구되었는지 확인"""
        return self.private_key_handle is not None

    def set_user_credentials(self, access_token: str, user_id: int, email: str):
        """로그인 성공 시 사용자 정보 저장"""
        self.access_token = access_token
        self.user_id = user_id
        self.email = email

    def set_key_pair(self, private_handle, public_handle):
        """복호화된 개인키/공개키 쌍 저장"""
        self.private_key_handle = private_handle
        self.public_key_handle = public_handle

    def get_private_key(self):
        """복호화된 개인키 반환"""
        if not self.private_key_handle:
            raise RuntimeError("개인키가 복구되지 않았습니다. 먼저 로그인하세요.")
        return self.private_key_handle

    def get_public_key(self):
        """복호화된 공개키 반환"""
        if not self.public_key_handle:
            raise RuntimeError("공개키가 로드되지 않았습니다. 먼저 로그인하세요.")
        return self.public_key_handle

    def cache_team_key(self, repo_id: int, aes_handle):
        """저장소의 팀 키를 메모리에 캐싱"""
        self.team_keys[repo_id] = aes_handle

    def get_cached_team_key(self, repo_id: int) -> Optional[any]:
        """캐시된 팀 키 조회 (없으면 None)"""
        return self.team_keys.get(repo_id)

    def clear_team_keys(self):
        """모든 팀 키 캐시 삭제"""
        self.team_keys.clear()

    def clear(self):
        """세션 전체 초기화 (로그아웃)"""
        self.access_token = None
        self.user_id = None
        self.email = None
        self.private_key_handle = None
        self.public_key_handle = None
        self.team_keys.clear()

    def __repr__(self):
        return (f"<Session user_id={self.user_id} email={self.email} "
                f"has_key={self.has_private_key()} "
                f"cached_repos={len(self.team_keys)}>")
