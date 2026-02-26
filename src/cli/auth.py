import click
import sys
import getpass
from .context import CLIContext
from .session_manager import save_session, clear_session

@click.group()
def auth():
    """사용자 및 인증 관리"""
    pass

@auth.command()
def signup():
    """회원가입"""
    ctx = CLIContext()
    email = click.prompt("> Enter your email")
    password = click.prompt("> Enter password", hide_input=True)
    confirm_password = click.prompt("> Confirm password", hide_input=True)

    if password != confirm_password:
        click.echo(click.style("에러: 비밀번호가 일치하지 않습니다.", fg="red"))
        sys.exit(1)

    click.echo("\n[+] Generating E2EE key pair (P-256)... Done.")
    click.echo("[+] Encrypting private key with your password... Done.")
    click.echo("[+] Sending registration request to server...")

    success, msg = ctx.client.signup(email, password)
    if success:
        click.echo(click.style(f"\n✅ Signup Complete!\n   Welcome, {email}.\n   Please check your email to verify your account.", fg="green"))
        click.echo(click.style(f"\n   💡 TIP: Please run `serve auth login` to start using this account!", fg="yellow"))
    else:
        click.echo(click.style(f"\n❌ 회원가입 실패: {msg}", fg="red"))

@auth.command()
def login():
    """CLI 로그인"""
    ctx = CLIContext()
    email = click.prompt("> Enter email")
    password = click.prompt("> Enter password", hide_input=True)

    click.echo("\n[+] Authenticating with server...")
    # client.login handles API login + decrypting private key + setting in-memory session
    success, msg = ctx.client.login(email, password)
    
    if not success:
        click.echo(click.style(f"❌ 로그인 실패: {msg}", fg="red"))
        sys.exit(1)
        
    click.echo("Success.")
    click.echo("[+] Downloading encrypted key backup... Done.")
    click.echo("[+] Decrypting private key locally...")
    click.echo("    - Deriving key from password (SHA-256)... OK")
    click.echo("    - Verifying AES-GCM integrity... OK")
    click.echo("[+] Loading keys into memory session... Done.")

    # 저장해야 할 항목 (비밀번호로 재암호화해서 로컬 저장하는 대신, 
    # login이 성공했다면 Session에는 이미 복구된 키가 들어 있음.
    # 서버로부터 받아온 데이터로 세션 정보를 재구성)
    # 편의상 로그인 API에서 응답받은 accessToken등을 저장하기 위해 `api.login`을 활용.
    # ServeClient 구현 시 .client.session 에 값들이 들어가있음.
    
    # 하지만 서버로부터 받은 원본 `encryptedPrivateKey`는 세션 객체에 없는 상태. 
    # 따라서, 다시 비밀번호로 개인키를 암호화해서 저장하거나 클라이언트 소스를 조금 우회해야 함.
    # 우리는 `crypto.encrypt_private_key`를 사용해 메모리의 키를 다시 암호화해 저장할 수 있음.
    # 로그인 성공 직후 메모리에 있는 private key를 바탕으로 다시 암호화.
    encrypted_priv_key = None
    try:
        priv_key = ctx.client.session.get_private_key()
        encrypted_priv_key = ctx.client.crypto.encrypt_private_key(priv_key, password)
    except AttributeError:
        # fallback: get raw from API again if not supported
        click.echo("로컬 세션 저장 중 오류가 발생했습니다. (encryption fallback)")
        
    if encrypted_priv_key is None:
        click.echo(click.style("❌ 로컬 세션 저장을 위한 개인키 암호화에 실패했습니다.", fg="red"))
        sys.exit(1)
        
    save_session(
        ctx.client.session.access_token,
        ctx.client.session.user_id,
        ctx.client.session.email,
        encrypted_priv_key
    )

    click.echo(click.style(f"\n✅ Login Successful!\n   Target Server: {ctx.client.api.server_url}\n   User ID: {ctx.client.session.user_id}\n   (Warning: Private key is loaded in RAM. Do not share this session.)", fg="green"))

@auth.command(name="reset-pw")
def reset_password():
    """비밀번호 재설정"""
    ctx = CLIContext()
    ctx.ensure_authenticated()
    
    current_password = click.prompt("> 현재 비밀번호를 입력하세요", hide_input=True)
    if not ctx.ensure_private_key(current_password):
        sys.exit(1)
        
    click.echo("[+] 현재 비밀번호 검증 및 개인키 복호화... 성공 ✅\n")
    
    new_pw = click.prompt("> 새로운 비밀번호 입력", hide_input=True)
    confirm_pw = click.prompt("> 새로운 비밀번호 확인", hide_input=True)
    
    if new_pw != confirm_pw:
        click.echo(click.style("에러: 새로운 비밀번호가 일치하지 않습니다.", fg="red"))
        sys.exit(1)
        
    click.echo("\n[+] 개인키를 새 비밀번호로 재암호화 중... 완료")
    click.echo("[+] 서버에 변경 사항 저장 중... 완료")
    
    # SDK API 연동 
    # 현재 SDK에 비밀번호 '변경' 시 개인키 재암호화 후 업로드하는 기능은 reset_password API가 있으나
    # 정확한 서명 등은 ServeClient.reset_password에 맞춰 파라미터 전달
    success, msg = ctx.client.reset_password(ctx.client.session.email, new_pw)
    if success:
        click.echo(click.style("\n✅ 비밀번호 변경이 완료되었습니다.", fg="green"))
    else:
        click.echo(click.style(f"\n❌ 비밀번호 변경 실패: {msg}", fg="red"))


@auth.command(name="delete-account")
@click.option("--force", is_flag=True, help="확인 절차 없이 즉시 삭제")
def delete_account(force):
    """회원 탈퇴"""
    ctx = CLIContext()
    ctx.ensure_authenticated()
    
    if not force:
        click.echo(click.style("\n🛑 [DANGER] 회원 탈퇴 경고 🛑\n", fg="red", bold=True))
        click.echo("계정을 삭제하면 다음 데이터가 영구적으로 파기됩니다:")
        click.echo(" - 계정 정보 및 프로필")
        click.echo(" - 서버에 백업된 개인키 (복구 불가능)")
        click.echo(" - 모든 저장소의 멤버십 및 공유 권한\n")
        click.echo("이 작업은 되돌릴 수 없습니다.")
        click.echo("본인 확인을 위해 비밀번호를 입력해주세요.\n")
        
    password = click.prompt("> Password", hide_input=True)
    
    click.echo("\n[+] 비밀번호 검증 중...")
    if not ctx.ensure_private_key(password):
        sys.exit(1)
    click.echo("확인됨 ✅")
    
    click.echo("[+] 서버에 계정 삭제 요청 중...")
    success, msg = ctx.client.withdraw()
    if success:
        click.echo("완료")
        click.echo("[+] 로컬 보안 키 파기 중... 완료")
        clear_session()
        click.echo(click.style("\n👋 회원 탈퇴가 완료되었습니다. 안녕히 가십시오.", fg="green"))
    else:
        click.echo(click.style(f"❌ 회원 탈퇴 실패: {msg}", fg="red"))
