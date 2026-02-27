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
    """데모 데이터 업로드"""
    ctx = CLIContext()
    ctx.ensure_private_key()  # Requires private key for encryption

    click.echo(f"[+] Uploading NPZ file '{npz_file}' as {data_id} for '{task_name}' in repository {team_id}...")
    
    # Check if file exists
    if not os.path.exists(npz_file):
        click.echo(click.style(f"❌ 파일을 찾을 수 없습니다: {npz_file}", fg="red"))
        return
    
    try:
        # Serialize NPZ file to chunks
        click.echo("[+] Reading and serializing NPZ file...")
        chunk_data = npz_to_chunks(npz_file)
        click.echo(f"[+] NPZ file split into {len(chunk_data)} chunks")
    except Exception as e:
        click.echo(click.style(f"❌ NPZ 파일 처리 실패: {e}", fg="red"))
        return
    
    # Upload encrypted chunks via SDK
    success, msg = ctx.client.upload_chunks_to_document(
        file_name=f"{task_name}_{data_id}",
        repo_id=team_id,
        chunks_data=chunk_data
    )
    
    if success:
        click.echo(click.style(f"✅ 데모 데이터 업로드 성공!", fg="green"))
    else:
        click.echo(click.style(f"❌ 데모 데이터 업로드 실패: {msg}", fg="red"))

@data.command()
@click.argument('team-id')
def list(team_id):
    """목록 조회"""
    ctx = CLIContext()
    ctx.ensure_authenticated()

    click.echo(f"[+] Fetching data list for repository {team_id}...")
    docs, msg = ctx.client.get_documents(team_id)
    
    if docs is None:
        click.echo(click.style(f"❌ 목록 조회 실패: {msg}", fg="red"))
        return
        
    if not docs:
        click.echo("저장소에 데이터가 없습니다.")
        return
        
    # Check local database for downloaded status
    downloaded_ids = set()
    
    # Check if a db-url was passed (we'll need to parse it if we want to support it in list, but list doesn't take db-url right now)
    # Defaulting to local.db in the current directory
    db_path = "local.db"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT data_id FROM downloaded_data WHERE team_id = ?", (team_id,))
            downloaded_ids = {row[0] for row in cursor.fetchall()}
            conn.close()
        except sqlite3.OperationalError:
            pass # Table might not exist yet
            
    click.echo("\n--- Demo Data List ---")
    for doc in docs:
        file_name = doc.get("fileName", "Unknown")
        uploader = doc.get("uploaderId", "Unknown")
        date = doc.get("uploadedAt", "Unknown")
        size = doc.get("size", "0")
        
        # fileName format is usually task_name_data_id
        parts = file_name.split("_", 1)
        data_id_part = parts[1] if len(parts) > 1 else file_name
        # The data_id itself might have parts if task_name had underscores, let's just check if data_id is in the file_name
        
        status = "Not Downloaded"
        for d_id in downloaded_ids:
            if d_id in file_name:
                status = "Downloaded"
                break
        
        click.echo(f"- 파일명: {file_name} | 업로더: {uploader} | 날짜: {date} | 크기: {size} bytes | 로컬상태: {status}")

@data.command()
@click.argument('team-id')
@click.argument('task-name')
@click.argument('data-id')
@click.option('--output', 'output_file', required=True, help="다운로드할 NPZ 파일 경로")
@click.option('--db-url', help="저장할 로컬 데이터베이스 연결 URL (기본값: sqlite:///local.db)", default="sqlite:///local.db")
def download(team_id, task_name, data_id, output_file, db_url):
    """데모 데이터 다운로드"""
    ctx = CLIContext()
    ctx.ensure_private_key()

    click.echo(f"[+] Downloading data {data_id} and saving to '{output_file}'...")
    # Download and decrypt chunks from server
    chunks, msg = ctx.client.download_chunks_from_document(f"{task_name}_{data_id}", team_id)
    
    if chunks is None:
        click.echo(click.style(f"❌ 다운로드 실패: {msg}", fg="red"))
        return
    
    # Reconstruct NPZ file from chunks
    try:
        click.echo(f"[+] Reconstructing NPZ file from {len(chunks)} chunks...")
        chunks_to_npz(chunks, output_file)
        click.echo(click.style(f"✅ NPZ 파일 복원 성공: {output_file}", fg="green"))
    except Exception as e:
        click.echo(click.style(f"❌ NPZ 파일 복원 실패: {e}", fg="red"))
        return
    
    # Save to local database tracking
    db_path = "local.db"
    if db_url.startswith("sqlite:///"):
        parsed_path = db_url.replace("sqlite:///", "")
        db_path = parsed_path
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloaded_data (
                team_id TEXT,
                task_name TEXT,
                data_id TEXT,
                output_file TEXT,
                download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_id, data_id)
            )
        ''')
        # Insert or replace record
        cursor.execute('''
            INSERT OR REPLACE INTO downloaded_data (team_id, task_name, data_id, output_file)
            VALUES (?, ?, ?, ?)
        ''', (team_id, task_name, data_id, output_file))
        
        conn.commit()
        conn.close()
        click.echo(click.style(f"✅ 로컬 DB 기록 완료!", fg="green"))
    except Exception as e:
        click.echo(click.style(f"⚠️ 데이터베이스 기록 중 오류 발생: {e}", fg="yellow"))

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

@data.command(name='upload-scenario')
@click.argument('team-id')
@click.argument('scenario-name')
@click.argument('scenario-dir', type=click.Path(exists=True))
@click.option('--description', help="시나리오 설명", default="")
@click.option('--force', is_flag=True, help="이미 업로드된 데모도 재업로드")
def upload_scenario(team_id, scenario_name, scenario_dir, description, force):
    """
    시나리오 단위로 여러 데모를 묶어서 암호화/업로드
    
    시나리오 디렉토리 구조:
    scenario_name/
        demo1/processed_demo.npz
        demo2/processed_demo.npz
        demo3/processed_demo.npz
    """
    ctx = CLIContext()
    ctx.ensure_private_key()
    
    scenario_path = Path(scenario_dir)
    click.echo(f"[+] Uploading scenario '{scenario_name}' from {scenario_path}...")
    
    # Find all processed_demo.npz files
    demo_files = list(scenario_path.rglob('processed_demo.npz'))
    
    if not demo_files:
        click.echo(click.style(f"❌ No processed_demo.npz files found in {scenario_path}", fg="red"))
        return
    
    click.echo(f"[+] Found {len(demo_files)} demo(s) in scenario")
    
    # Upload each demo with scenario prefix
    success_count = 0
    fail_count = 0
    
    for demo_file in demo_files:
        # Extract demo ID from path
        rel_path = demo_file.relative_to(scenario_path)
        demo_id = rel_path.parent.name if rel_path.parent != Path('.') else 'demo'
        
        click.echo(f"\n[+] Processing {demo_id}...")
        
        # Validate NPZ format
        valid, errors = validate_npz(str(demo_file), strict=False)
        if not valid:
            click.echo(click.style(f"  ⚠️  Validation warnings:", fg="yellow"))
            for err in errors[:3]:  # Show first 3 errors
                click.echo(click.style(f"    - {err}", fg="yellow"))
            if not force:
                click.echo(click.style(f"  ❌ Skipping (use --force to upload anyway)", fg="red"))
                fail_count += 1
                continue
        
        try:
            # Serialize NPZ to chunks
            chunk_data = npz_to_chunks(str(demo_file))
            
            # Upload with scenario prefix
            file_name = f"{scenario_name}_{demo_id}"
            success, msg = ctx.client.upload_chunks_to_document(
                file_name=file_name,
                repo_id=team_id,
                chunks_data=chunk_data
            )
            
            if success:
                click.echo(click.style(f"  ✅ Uploaded: {file_name}", fg="green"))
                success_count += 1
            else:
                click.echo(click.style(f"  ❌ Failed: {msg}", fg="red"))
                fail_count += 1
        
        except Exception as e:
            click.echo(click.style(f"  ❌ Error: {e}", fg="red"))
            fail_count += 1
    
    # Summary
    click.echo(f"\n{'='*60}")
    click.echo(f"Scenario upload complete: {success_count} succeeded, {fail_count} failed")
    if success_count > 0:
        click.echo(click.style(f"✅ Successfully uploaded {success_count} demo(s) for scenario '{scenario_name}'", fg="green"))

