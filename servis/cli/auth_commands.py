import typer
from rich.console import Console
import json
from pathlib import Path

from servis.serve_sdk.client import ServeClient
from servis.core.config import CLOUD_URL

app = typer.Typer(help="계정 인증 및 로그인 관리")
console = Console()

# 로그인 정보를 임시로 저장할 파일 경로
CREDENTIALS_FILE = Path.home() / ".servis" / "credentials.json"

@app.command("login")
def login(
    email: str = typer.Option(..., prompt="📧 이메일", help="SeRVe 계정 이메일"),
    password: str = typer.Option(..., prompt="🔑 비밀번호", hide_input=True, help="SeRVe 계정 비밀번호")
):
    """SeRVe 서버에 로그인합니다."""
    console.print("[bold blue]서버에 로그인 중...[/bold blue]")
    client = ServeClient(server_url=CLOUD_URL)
    
    # 팀원이 만든 SDK의 정식 로그인 함수 호출
    success, msg = client.login(email=email, password=password)
    
    if success:
        # 로그인 성공 시, 다음 명령어를 위해 이메일/비밀번호를 로컬 파일에 임시 저장
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        creds = {
            "email": email,
            "password": password
        }
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(creds, f)
        
        console.print("[bold green]✅ 로그인 성공![/bold green]")
        console.print("💡 이제 'servis repo list' 등의 명령어를 사용할 수 있습니다.")
    else:
        console.print(f"[bold red]❌ 로그인 실패:[/bold red] {msg}")

@app.command("logout")
def logout():
    """저장된 로그인 정보를 삭제하고 로그아웃합니다."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()
        console.print("[bold green]✅ 성공적으로 로그아웃 되었습니다.[/bold green]")
    else:
        console.print("[yellow]💡 이미 로그아웃 상태이거나 로그인 정보가 없습니다.[/yellow]")