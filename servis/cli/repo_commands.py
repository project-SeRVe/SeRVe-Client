import typer
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

from servis.serve_sdk.client import ServeClient
from servis.core.config import CLOUD_URL

app = typer.Typer(help="팀 저장소(Repository) 및 멤버 관리 명령어")
console = Console()

def get_client() -> ServeClient:
    """저장된 로그인 정보를 불러와 클라이언트를 준비합니다."""
    cred_file = Path.home() / ".servis" / "credentials.json"
    
    if not cred_file.exists():
        console.print("[bold red]❌ 로그인 정보가 없습니다.[/bold red] [yellow]'servis login'[/yellow][bold red]을 먼저 실행해주세요.[/bold red]")
        raise typer.Exit(1)
        
    # 파일에서 이메일/비밀번호 읽어오기
    with open(cred_file, "r", encoding="utf-8") as f:
        creds = json.load(f)
        
    email = creds.get("email")
    password = creds.get("password")
    
    client = ServeClient(server_url=CLOUD_URL)
    
    # 실제 서버에 로그인하여 토큰 및 개인키 복호화 진행
    success, msg = client.login(email=email, password=password)
    
    if not success:
        console.print(f"[bold red]❌ 세션 만료 또는 로그인 실패:[/bold red] {msg}")
        console.print("[yellow]💡 'servis login' 명령어로 다시 로그인해주세요.[/yellow]")
        raise typer.Exit(1)
        
    return client

@app.command("create")
def create(
    team_name: str = typer.Argument(..., help="생성할 저장소 이름"),
    description: str = typer.Option("", help="저장소에 대한 설명")
):
    """새로운 팀 저장소를 생성합니다."""
    client = get_client()
    console.print(f"[bold blue]저장소 생성 요청 중...[/bold blue] ({team_name})")
    
    repo_id, msg = client.create_repository(name=team_name, description=description)
    if repo_id:
        console.print(f"[bold green]✅ 성공:[/bold green] {msg}")
    else:
        console.print(f"[bold red]❌ 실패:[/bold red] {msg}")

@app.command("list")
def list_repos():
    """사용자가 속한 모든 저장소 목록을 조회합니다."""
    client = get_client()
    console.print("[bold blue]저장소 목록 조회 중...[/bold blue]")
    
    success, data = client.get_my_repositories()
    if not success:
        console.print(f"[bold red]❌ 조회 실패:[/bold red] {data}")
        return
        
    table = Table(title="참여 중인 저장소 목록")
    table.add_column("Team ID", style="cyan")
    table.add_column("Team Name", style="magenta")
    table.add_column("Description", style="white")
    table.add_column("My Role", style="green")
    
    for repo in data:
        table.add_row(
            str(repo.get('id', '')), 
            repo.get('name', ''), 
            repo.get('description', ''),
            repo.get('myRole', 'UNKNOWN')
        )
    console.print(table)

@app.command("invite")
def invite(
    team_id: str = typer.Argument(..., help="저장소 이름이나 ID"),
    user_email: str = typer.Argument(..., help="초대할 사용자의 이메일")
):
    """특정 저장소에 새로운 멤버를 초대합니다."""
    client = get_client()
    console.print(f"[bold blue]멤버 초대 중...[/bold blue] ({user_email} -> {team_id})")
    
    success, msg = client.invite_member(repo_id=team_id, email=user_email)
    if success:
        console.print(f"[bold green]✅ 성공:[/bold green] {msg}")
    else:
        console.print(f"[bold red]❌ 실패:[/bold red] {msg}")

@app.command("kick")
def kick(
    team_id: str = typer.Argument(..., help="저장소 이름이나 ID"),
    user_id: str = typer.Argument(..., help="강퇴할 멤버 ID")
):
    """멤버를 강퇴하고 보안 키를 자동 로테이션합니다."""
    client = get_client()
    console.print(f"[bold blue]멤버 강퇴 요청 중...[/bold blue] ({user_id})")
    
    success, msg = client.kick_member(repo_id=team_id, target_user_id=user_id)
    if success:
        console.print(f"[bold green]✅ 성공:[/bold green] {msg}")
    else:
        console.print(f"[bold red]❌ 실패:[/bold red] {msg}")

@app.command("set-role")
def set_role(
    team_id: str = typer.Argument(..., help="저장소 이름이나 ID"),
    user_id: str = typer.Argument(..., help="권한을 변경할 멤버 ID"),
    role: str = typer.Argument(..., help="부여할 권한 (예: ADMIN, MEMBER)")
):
    """특정 멤버의 권한을 변경합니다."""
    client = get_client()
    console.print(f"[bold blue]권한 변경 중...[/bold blue] ({user_id} -> {role})")
    
    success, msg = client.update_member_role(repo_id=team_id, target_user_id=user_id, new_role=role)
    if success:
        console.print(f"[bold green]✅ 성공:[/bold green] {msg}")
    else:
        console.print(f"[bold red]❌ 실패:[/bold red] {msg}")

@app.command("show")
def show(
    team_id: str = typer.Argument(..., help="상세 조회할 저장소 이름이나 ID")
):
    """저장소 상세 정보 및 멤버 목록을 조회합니다."""
    client = get_client()
    console.print(f"[bold blue]저장소 상세 정보 불러오는 중...[/bold blue] ({team_id})")
    
    success, repos = client.get_my_repositories()
    if not success:
        console.print(f"[bold red]❌ 저장소 정보 조회 실패:[/bold red] {repos}")
        return
        
    target_repo = next((repo for repo in repos if str(repo.get('id')) == team_id or repo.get('name') == team_id), None)
    if not target_repo:
        console.print(f"[bold red]❌ 오류:[/bold red] '{team_id}' 저장소를 찾을 수 없거나 접근 권한이 없습니다.")
        return

    success, members = client.get_members(repo_id=str(target_repo.get('id')))
    if not success:
        console.print(f"[bold red]❌ 멤버 목록 조회 실패:[/bold red] {members}")
        return

    my_role = target_repo.get('myRole', 'UNKNOWN')
    role_color = "bold red" if my_role == "ADMIN" else "bold green"
    
    console.print("\n[bold cyan]📦 Repository Info[/bold cyan]")
    console.print(f"  • [bold]Team Name:[/bold] {target_repo.get('name', 'N/A')}")
    console.print(f"  • [bold]Team ID:[/bold]   {target_repo.get('id', 'N/A')}")
    if target_repo.get('description'):
        console.print(f"  • [bold]Desc:[/bold]      {target_repo.get('description')}")
    console.print(f"  • [bold]My Role:[/bold]   [{role_color}]{my_role}[/{role_color}]\n")

    table = Table(title="👥 Member List")
    table.add_column("User ID", style="cyan")
    table.add_column("Email", style="magenta")
    table.add_column("Role", style="green")
    
    for member in members:
        is_me = " (Me)" if str(member.get('userId')) == str(client.session.user_id) else ""
        table.add_row(
            str(member.get('userId', '')), 
            f"{member.get('email', 'N/A')}{is_me}", 
            member.get('role', 'UNKNOWN')
        )
    console.print(table)

@app.command("rotate-key")
def rotate_key(
    team_id: str = typer.Argument(..., help="저장소 이름이나 ID")
):
    """팀 보안 키를 수동으로 로테이션(갱신)합니다."""
    client = get_client()
    console.print(f"[bold blue]보안 키 수동 갱신 중...[/bold blue] ({team_id})")
    console.print("[yellow]⚠️ 현재 SDK 버전에서는 kick 명령어 사용 시 키가 자동 로테이션됩니다. 수동 로테이션 API 연동은 추가 개발이 필요합니다.[/yellow]")