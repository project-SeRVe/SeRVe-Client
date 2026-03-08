import typer
from servis.cli import repo_commands, auth_commands

app = typer.Typer(
    help="SeRViS: Secure Robot VLA Sharing & Inference CLI",
    add_completion=False
)

# 명령어 그룹 등록
app.add_typer(repo_commands.app, name="repo", help="저장소 및 팀 관리")
app.add_typer(auth_commands.app, name="auth", help="계정 및 인증 관리")

# 편의를 위해 루트 명령어(servis login)로도 바로 쓸 수 있게 꺼내기
app.command("login")(auth_commands.login)
app.command("logout")(auth_commands.logout)

if __name__ == "__main__":
    app()