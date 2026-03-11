import click
from rich.console import Console
from rich.table import Table
from .context import CLIContext

console = Console()

@click.group()
def repo():
    """저장소 관리"""
    pass

@repo.command()
@click.argument('team-name')
@click.option('--description', help="저장소에 대한 설명", default="")
def create(team_name, description):
    """저장소 생성"""
    ctx = CLIContext()
    ctx.ensure_private_key()

    console.print(f"[bold blue]저장소 생성 요청 중...[/bold blue] ({team_name})")
    repo_id, msg = ctx.client.create_repository(team_name, description)
    
    if repo_id:
        console.print(f"[bold green]✅ 성공:[/bold green] {msg}")
    else:
        console.print(f"[bold red]❌ 실패:[/bold red] {msg}")

@repo.command()
def list():
    """저장소 목록 조회"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    console.print("[bold blue]저장소 목록 조회 중...[/bold blue]")
    repos, msg = ctx.client.get_my_repositories()
    
    if repos is None:
        console.print(f"[bold red]❌ 조회 실패:[/bold red] {msg}")
        return
        
    if not repos:
        console.print("참여 중인 저장소가 없습니다.")
        return
    
    table = Table(title="참여 중인 저장소 목록")
    table.add_column("Team ID", style="cyan")
    table.add_column("Team Name", style="magenta")
    table.add_column("Description", style="white")
    table.add_column("My Role", style="green")
    
    for r in repos:
        table.add_row(
            str(r.get('id', '')), 
            r.get('name', ''), 
            r.get('description', ''),
            r.get('role', 'UNKNOWN')
        )
    console.print(table)

@repo.command()
@click.argument('team-id')
def show(team_id):
    """저장소 상세 조회"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    console.print(f"[bold blue]저장소 상세 정보 불러오는 중...[/bold blue] ({team_id})")
    
    # 저장소 정보 조회
    repos, msg = ctx.client.get_my_repositories()
    if repos is None:
        console.print(f"[bold red]❌ 저장소 정보 조회 실패:[/bold red] {msg}")
        return
        
    target_repo = next((repo for repo in repos if str(repo.get('id')) == team_id or repo.get('name') == team_id), None)
    if not target_repo:
        console.print(f"[bold red]❌ 오류:[/bold red] '{team_id}' 저장소를 찾을 수 없거나 접근 권한이 없습니다.")
        return

    # 멤버 목록 조회
    members, members_msg = ctx.client.get_members(str(target_repo.get('id')))
    if members is None:
        console.print(f"[bold red]❌ 멤버 목록 조회 실패:[/bold red] {members_msg}")
        return

    my_role = target_repo.get('role', 'UNKNOWN')
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
        user_id = str(member.get('userId', ''))
        is_me = " (Me)" if user_id == str(ctx.session_data.get('user_id')) else ""
        table.add_row(
            user_id, 
            f"{member.get('email', 'N/A')}{is_me}", 
            member.get('role', 'UNKNOWN')
        )
    console.print(table)

@repo.command()
@click.argument('team-id')
@click.argument('email')
def invite(team_id, email):
    """멤버 초대 (이메일 단위)"""
    ctx = CLIContext()
    ctx.ensure_private_key()

    console.print(f"[bold blue]멤버 초대 중...[/bold blue] ({email} -> {team_id})")
    success, msg = ctx.client.invite_member(team_id, email)
    
    if success:
        console.print(f"[bold green]✅ 성공:[/bold green] {msg}")
    else:
        console.print(f"[bold red]❌ 실패:[/bold red] {msg}")

@repo.command()
@click.argument('team-id')
@click.argument('user-id')
def kick(team_id, user_id):
    """멤버 강퇴 및 보안 키 자동 로테이션"""
    ctx = CLIContext()
    ctx.ensure_private_key()

    console.print(f"[bold blue]멤버 강퇴 요청 중...[/bold blue] ({user_id})")
    success, msg = ctx.client.kick_member(team_id, user_id)
    
    if success:
        console.print(f"[bold green]✅ 성공:[/bold green] {msg}")
        console.print("[yellow]💡 보안 키가 자동으로 로테이션되었습니다.[/yellow]")
    else:
        console.print(f"[bold red]❌ 실패:[/bold red] {msg}")

@repo.command(name="set-role")
@click.argument('team-id')
@click.argument('user-id')
@click.argument('role')
def set_role(team_id, user_id, role):
    """권한 변경"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    console.print(f"[bold blue]권한 변경 중...[/bold blue] ({user_id} -> {role})")
    success, msg = ctx.client.update_member_role(team_id, user_id, role)
    
    if success:
        console.print(f"[bold green]✅ 성공:[/bold green] {msg}")
    else:
        console.print(f"[bold red]❌ 실패:[/bold red] {msg}")
