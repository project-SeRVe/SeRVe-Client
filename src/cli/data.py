import click
import sqlite3
import os
from .context import CLIContext

@click.group()
def data():
    """데모 데이터 관리"""
    pass

@data.command()
@click.argument('team-id')
@click.argument('task-name')
@click.argument('data-id')
@click.option('--description', help="작업에 대한 설명", default="")
@click.option('--robot-id', help="작업의 출처(로봇 id)", default="")
def upload(team_id, task_name, data_id, description, robot_id):
    """데모 데이터 업로드"""
    ctx = CLIContext()
    ctx.ensure_private_key()  # Requires private key for encryption

    click.echo(f"[+] Uploading {data_id} for '{task_name}' in repository {team_id}...")
    # The spec dictates: "[description]", "[robot-id]".
    # Because vector chunking is file-based in ServeClient (`upload_chunks_to_document` or `upload_document`),
    # we simulate the demo upload by serializing the metadata.
    
    metadata = f"Task: {task_name}\nDataID: {data_id}\nDesc: {description}\nRobotID: {robot_id}"
    
    # Simulate a chunk for demo purposes
    chunk_data = [{"chunkIndex": 0, "data": metadata}]
    
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
@click.option('--db-url', help="저장할 로컬 데이터베이스 연결 URL (기본값: sqlite:///local.db)", default="sqlite:///local.db")
def download(team_id, task_name, data_id, db_url):
    """데모 데이터 다운로드"""
    ctx = CLIContext()
    ctx.ensure_private_key()

    click.echo(f"[+] Downloading data {data_id} to database '{db_url}'...")
    # Map to `download_chunks_from_document` in client (which uses sync under the hood)
    chunks, msg = ctx.client.download_chunks_from_document(f"{task_name}_{data_id}", team_id)
    
    if chunks is None:
         click.echo(click.style(f"❌ 다운로드 실패: {msg}", fg="red"))
    else:
         # Save to local database
         db_path = "local.db"
         if db_url.startswith("sqlite:///"):
             parsed_path = db_url.replace("sqlite:///", "")
             # If it's an absolute path (e.g. sqlite:////tmp/local.db), it will have a leading slash after replace
             # If it was sqlite:///local.db, it will be local.db
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
                     download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     UNIQUE(team_id, data_id)
                 )
             ''')
             # Insert or replace record
             cursor.execute('''
                 INSERT OR REPLACE INTO downloaded_data (team_id, task_name, data_id)
                 VALUES (?, ?, ?)
             ''', (team_id, task_name, data_id))
             
             # Example of storing actual chunk locally could be added here
             
             conn.commit()
             conn.close()
         except Exception as e:
             click.echo(click.style(f"⚠️ 데이터베이스 기록 중 오류 발생: {e}", fg="yellow"))
         
         click.echo(click.style(f"✅ 다운로드 완료! (복호화된 청크 수: {len(chunks)})", fg="green"))
         # Extract first chunk data to show preview
         if len(chunks) > 0:
             preview = chunks[0].get("data", "")[:50].replace('\n', ' ')
             click.echo(f"   [Preview]: {preview}...")

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
