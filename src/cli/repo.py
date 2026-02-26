import click
from .context import CLIContext

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

    click.echo(f"[+] Creating repository '{team_name}'...")
    repo_id, msg = ctx.client.create_repository(team_name, description)
    
    if repo_id:
        click.echo(click.style(f"✅ 저장소 생성 성공! (ID: {repo_id})", fg="green"))
    else:
        click.echo(click.style(f"❌ 저장소 생성 실패: {msg}", fg="red"))

@repo.command()
def list():
    """저장소 목록 조회"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    click.echo("[+] Fetching repository list...")
    repos, msg = ctx.client.get_my_repositories()
    
    if repos is None:
        click.echo(click.style(f"❌ 조회 실패: {msg}", fg="red"))
        return
        
    if not repos:
        click.echo("참여 중인 저장소가 없습니다.")
        return
        
    click.echo(f"\n총 {len(repos)}개의 저장소:")
    for r in repos:
        desc = r.get("description", "설명 없음")
        # Handle dict or string response appropriately based on ServeClient
        click.echo(f"- 팀 ID: {r.get('id')} | 이름: {r.get('name')} | 권한: {r.get('role', 'N/A')} | 설명: {desc}")

@repo.command()
@click.argument('team-id') # The spec says team-name or id, but team-id is usually required by SDK
@click.argument('email')
def invite(team_id, email):
    """멤버 초대 (이메일 단위)"""
    ctx = CLIContext()
    ctx.ensure_private_key()

    click.echo(f"[+] Inviting {email} to repository {team_id}...")
    success, msg = ctx.client.invite_member(team_id, email)
    
    if success:
        click.echo(click.style(f"✅ 멤버 초대 성공: {msg}", fg="green"))
    else:
        click.echo(click.style(f"❌ 멤버 초대 실패: {msg}", fg="red"))

@repo.command()
@click.argument('team-id')
@click.argument('user-id')
def kick(team_id, user_id):
    """멤버 강퇴"""
    ctx = CLIContext()
    ctx.ensure_private_key()

    click.echo(f"[+] Kicking {user_id} from repository {team_id}...")
    success, msg = ctx.client.kick_member(team_id, user_id)
    
    if success:
        click.echo(click.style(f"✅ 멤버 강퇴 성공: {msg}", fg="green"))
    else:
        click.echo(click.style(f"❌ 멤버 강퇴 실패: {msg}", fg="red"))

@repo.command(name="rotate-key")
@click.argument('team-id')
def rotate_key(team_id):
    """팀 키 로테이션"""
    ctx = CLIContext()
    ctx.ensure_private_key()
    # SDK does not expose standalone rotate-key natively out of the box (it's inside kick_member), 
    # but there might be an API hook. If not, we might need a dummy message or SDK implementation update.
    # Note: `serve_sdk/client.py` does not have a public `rotate_team_key(repo_id)` method except inside kick_member.
    # We will invoke the API if available or mock it for now.
    click.echo(f"[+] Rotating team keys for {team_id}...")
    # Mocking SDK call since there is no `rotate_team_key` exposed publicly:
    # A complete implementation would add this to serve_sdk/client.py
    click.echo(click.style(f"✅ 키 로테이션 성공 (This is a stub, require API support in SDK)", fg="yellow"))

@repo.command(name="set-role")
@click.argument('team-id')
@click.argument('user-id')
@click.argument('role')
def set_role(team_id, user_id, role):
    """권한 변경"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    click.echo(f"[+] Setting role '{role}' for {user_id} in {team_id}...")
    success, msg = ctx.client.update_member_role(team_id, user_id, role)
    
    if success:
        click.echo(click.style(f"✅ 권한 변경 성공: {msg}", fg="green"))
    else:
        click.echo(click.style(f"❌ 권한 변경 실패: {msg}", fg="red"))

@repo.command()
@click.argument('team-id')
def show(team_id):
    """저장소 상세 조회"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    click.echo(f"[+] Fetching details for repository {team_id}...")
    # Fetch Members
    members, msg = ctx.client.get_members(team_id)
    if members is None:
        click.echo(click.style(f"❌ 조회 실패: {msg}", fg="red"))
        return
        
    click.echo("\n--- Repository Info ---")
    click.echo(f"Team ID: {team_id}")
    # Other metadata might require a specific team info API
    
    click.echo("\n--- Member List ---")
    if not members:
        click.echo("멤버가 없습니다.")
    else:
        for m in members:
            click.echo(f"- 이름/ID: {m.get('userId')} | 권한: {m.get('role')}")
