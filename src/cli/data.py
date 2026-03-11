import builtins
import click
import sqlite3
import os
from pathlib import Path
from .context import CLIContext
from .npz_utils import npz_to_chunks, chunks_to_npz
from .npz_validator import validate_npz
from .preprocess import preprocess_command
from .validate import validate_command
from .review import review_command
from .build_index import build_index_command

@click.group()
def data():
    """데모 데이터 관리"""
    pass

# Register preprocess command
data.add_command(preprocess_command)
data.add_command(validate_command)
data.add_command(review_command)
data.add_command(build_index_command)

@data.command()
@click.argument('team-id')
@click.argument('task-name')
@click.argument('data-id')
@click.option('--file', 'npz_file', required=True, help="로봇 trajectory npz 파일 경로")
@click.option('--description', help="작업에 대한 설명", default="")
@click.option('--robot-id', help="작업의 출처(로봇 id)", default="")
def upload(team_id, task_name, data_id, npz_file, description, robot_id):
    """단일 Task 데이터 업로드"""
    ctx = CLIContext()
    ctx.ensure_private_key()  # Requires private key for encryption

    click.echo(f"[+] Uploading NPZ file '{npz_file}' as task for repository {team_id}...")
    
    # Check if file exists
    if not os.path.exists(npz_file):
        click.echo(click.style(f"❌ 파일을 찾을 수 없습니다: {npz_file}", fg="red"))
        return
    
    try:
        # Read NPZ file and encode to base64
        click.echo("[+] Reading NPZ file...")  
        with open(npz_file, 'rb') as f:
            npz_binary = f.read()
        import base64
        npz_base64 = base64.b64encode(npz_binary).decode('utf-8')
        click.echo(f"[+] NPZ file size: {len(npz_binary)} bytes")
    except Exception as e:
        click.echo(click.style(f"❌ NPZ 파일 읽기 실패: {e}", fg="red"))
        return
    
    # Upload via SDK
    success, msg = ctx.client.upload_task(
        team_id=team_id,
        file_name=task_name,
        npz_data=npz_base64
    )
    
    if success:
        click.echo(click.style(f"✅ Task 업로드 성공!", fg="green"))
    else:
        click.echo(click.style(f"❌ Task 업로드 실패: {msg}", fg="red"))

@data.command()
@click.argument('team-id')
def list(team_id):
    """Task 목록 조회"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    click.echo(f"[+] Fetching task list for repository {team_id}...")
    tasks, msg = ctx.client.get_tasks(team_id)
    
    if tasks is None:
        click.echo(click.style(f"❌ 목록 조회 실패: {msg}", fg="red"))
        return
        
    if not tasks:
        click.echo("저장소에 task가 없습니다.")
        return
        
    # TODO: Check local database for downloaded status (if needed)
    # For now, just display the task list
            
    click.echo("\n--- Task List ---")
    for task in tasks:
        file_name = task.get("fileName", "Unknown")
        task_id = task.get("id", "Unknown")
        uploader = task.get("uploaderId", "Unknown")
        date = task.get("uploadedAt", "Unknown")
        
        click.echo(f"  [{task_id}] {file_name}")

@data.command()
@click.argument('team-id')
@click.argument('task-id', type=int)
@click.option('--output', 'output_file', required=True, help="다운로드할 NPZ 파일 경로")
def download(team_id, task_id, output_file):
    """태스크 데이터 다운로드"""
    ctx = CLIContext()
    ctx.ensure_private_key()

    click.echo(f"[+] Downloading task {task_id} and saving to '{output_file}'...")
    
    # Download task using Task API
    npz_data, msg = ctx.client.download_task(task_id, team_id)
    
    if npz_data is None:
        click.echo(click.style(f"❌ 다운로드 실패: {msg}", fg="red"))
        return
    
    # Save NPZ file
    try:
        import base64
        click.echo(f"[+] Saving NPZ file...")
        with open(output_file, 'wb') as f:
            f.write(base64.b64decode(npz_data))
        click.echo(click.style(f"✅ NPZ 파일 저장 성공: {output_file}", fg="green"))
    except Exception as e:
        click.echo(click.style(f"❌ NPZ 파일 저장 실패: {e}", fg="red"))
        return
@data.command()
@click.argument('team-id')
@click.argument('db-url')
def pull(team_id, db_url):
    """데모 데이터 동기화"""
    ctx = CLIContext()
    ctx.ensure_private_key()

    click.echo(f"[+] Syncing data for repository {team_id} to database '{db_url}'...")
    
    success, chunks_or_msg = ctx.client.sync_team_chunks(team_id, -1)
    if success:
         click.echo(click.style(f"✅ 동기화 완료! (가져온 암호화 청크 수: {len(chunks_or_msg)})", fg="green"))
    else:
         click.echo(click.style(f"❌ 동기화 실패: {chunks_or_msg}", fg="red"))

