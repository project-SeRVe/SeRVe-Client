"""
SeRVe SDK - Zero-Trust Document Sharing Client

End-to-End 암호화를 지원하는 문서 공유 플랫폼 클라이언트 SDK

사용법:
    from serve_sdk import ServeClient

    client = ServeClient(server_url="http://localhost:8080")
    client.login("user@example.com", "password")
    client.create_repository("MyRepo", "Description")
    client.upload_document("secret content", repo_id=1)

주요 기능:
- Zero-Trust 아키텍처: 서버는 평문 데이터를 절대 보지 못함
- Lazy Loading: 필요할 때만 키를 로드하여 메모리 효율성 극대화
- 자동 키 관리: 사용자는 암호화를 의식하지 않고 API만 호출
"""

from .client import ServeClient
from .session import Session
from .security import CryptoUtils

__version__ = "2.0.0"
__all__ = ["ServeClient", "Session", "CryptoUtils"]
