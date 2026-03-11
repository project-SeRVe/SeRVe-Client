import click
import sys
import getpass
from pathlib import Path
from .session_manager import get_session, save_session, clear_session
# Add project root to sys.path so we can import serve_sdk
# (Assuming src/cli/auth.py, root is ../..)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from serve_sdk.client import ServeClient

import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class CLIContext:
    def __init__(self):
        # Allow overriding the server URL via environment variable
        server_url = os.environ.get("SERVE_API_URL", "http://localhost:8080")
        self.client = ServeClient(server_url=server_url)
        self.session_data = get_session()
        
    def ensure_authenticated(self):
        if not self.session_data:
            click.echo(click.style("에러: 로그인이 필요합니다. 'serve auth login'을 먼저 실행하세요.", fg="red"), err=True)
            sys.exit(1)
            
        # Restore session data to SDK client so it can make authenticated API calls
        self.client.session.set_user_credentials(
            self.session_data["access_token"],
            self.session_data["user_id"],
            self.session_data["email"]
        )
        
    def ensure_private_key(self, password=None):
        """
        SDK에 사용할 개인키를 메모리에 로드하기 위해 입력받은 비밀번호로 복호화.
        Zero-trust 원칙에 따라 매번 명령어마다 필요한 시점에 복호화함.
        """
        self.ensure_authenticated()
        
        if self.client.session.has_private_key():
            return
            
        enc_priv_key = self.session_data.get("encrypted_private_key")
        if not enc_priv_key:
            click.echo(click.style("에러: 로컬 세션에 암호화된 개인키가 없습니다. 다시 로그인하세요.", fg="red"), err=True)
            sys.exit(1)
            
        if not password:
            password = getpass.getpass("> 현재 비밀번호를 입력하세요: ")
            
        try:
            # 복호화 시도
            private_key = self.client.crypto.recover_private_key(enc_priv_key, password)
            public_key = private_key.public_keyset_handle()
            self.client.session.set_key_pair(private_key, public_key)
            return True
        except Exception as e:
            click.echo(click.style(f"에러: 비밀번호가 틀렸거나 개인키 복호화에 실패했습니다.", fg="red"), err=True)
            sys.exit(1)
