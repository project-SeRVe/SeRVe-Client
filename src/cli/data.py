import builtins
import click
import sqlite3
import os
import json
from pathlib import Path
from serve_sdk.local_db import get_default_db
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
@click.argument('npz-file', type=click.Path(exists=True))
@click.option('--prompt', help="Scenario 식별용 프롬프트 (미지정시 episode_meta.json의 task_description 사용)")
@click.option('--kind', default="processed", help="Artifact 종류 (processed/raw)")
def upload(team_id, npz_file, prompt, kind):
    """
    Artifact 업로드 (새 서버 스펙)
    
    NPZ 파일과 같은 디렉토리의 episode_meta.json에서 메타데이터를 읽어
    서버에 전송하고, presigned URL로 S3에 직접 업로드합니다.
    """
    ctx = CLIContext()
    ctx.ensure_private_key()

    click.echo(f"[+] Uploading artifact '{npz_file}' to team {team_id}...")
    
    try:
        npz_path = Path(npz_file)
        meta_path = npz_path.parent / "episode_meta.json"
        
        if not meta_path.exists():
            click.echo(click.style(f"❌ episode_meta.json 파일을 찾을 수 없습니다: {meta_path}", fg="red"))
            return
        
        click.echo(f"[+] Reading metadata from {meta_path}...")
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        
        prompt_text = prompt if prompt else meta.get('task_description')
        if not prompt_text:
            click.echo(click.style("❌ --prompt 옵션 또는 episode_meta.json의 task_description이 필요합니다", fg="red"))
            return
        
        num_steps = meta.get('num_steps')
        state_dim = meta.get('state_dim')
        action_dim = meta.get('action_dim')
        
        image_size = meta.get('image_size', [])
        image_h = image_size[0] if len(image_size) > 0 else None
        image_w = image_size[1] if len(image_size) > 1 else None
        
        embed_dim = None
        embed_model_id = None
        
        click.echo(f"  - Task: {prompt_text}")
        click.echo(f"  - Steps: {num_steps}, State: {state_dim}, Action: {action_dim}")
        click.echo(f"  - Image: {image_h}x{image_w}")
        if meta.get('source_repo'):
            click.echo(f"  - Source: {meta['source_repo']} (episode {meta.get('source_episode_index', 'N/A')})")
        
    except json.JSONDecodeError as e:
        click.echo(click.style(f"❌ episode_meta.json 파싱 실패: {e}", fg="red"))
        return
    except Exception as e:
        click.echo(click.style(f"❌ 메타데이터 읽기 실패: {e}", fg="red"))
        return
    
    success, artifact_id = ctx.client.upload_artifact(
        team_id=team_id,
        npz_path=npz_file,
        prompt_text=prompt_text,
        num_steps=num_steps,
        state_dim=state_dim,
        action_dim=action_dim,
        image_h=image_h,
        image_w=image_w,
        embed_dim=embed_dim,
        embed_model_id=embed_model_id,
        kind=kind
    )
    
    if success:
        click.echo(click.style(f"✅ Artifact 업로드 성공!", fg="green"))
        click.echo(f"   Artifact ID: {artifact_id}")
    else:
        click.echo(click.style(f"❌ 업로드 실패: {artifact_id}", fg="red"))

@data.command()
@click.argument('demo-id')
def list(demo_id):
    """
    Demo의 Artifact 목록 조회 (새 서버 스펙)
    
    특정 Demo에 속한 Artifact 목록을 조회합니다.
    Note: 현재 서버는 Team 전체 Artifact 목록 조회 API가 없어 Demo ID가 필요합니다.
    """
    ctx = CLIContext()
    ctx.ensure_authenticated()

    click.echo(f"[+] Fetching artifact list for demo {demo_id}...")
    
    success, result = ctx.client.get_demo_artifacts(demo_id)
    
    if not success:
        click.echo(click.style(f"❌ 목록 조회 실패: {result}", fg="red"))
        return
    
    artifacts = result
    
    if not artifacts:
        click.echo("Demo에 artifact가 없습니다.")
        return
    
    click.echo("\n--- Artifact List ---")
    for artifact in artifacts:
        artifact_id = artifact.get("artifactId", "Unknown")
        kind = artifact.get("kind", "Unknown")
        size = artifact.get("size", 0)
        created_at = artifact.get("createdAt", "Unknown")
        
        click.echo(f"  [{artifact_id}]")
        click.echo(f"    Kind: {kind}")
        click.echo(f"    Size: {size} bytes")
        click.echo(f"    Created: {created_at}")

@data.command()
@click.argument('artifact-id')
@click.option('--output', 'output_file', required=True, help="다운로드할 NPZ 파일 경로")
def download(artifact_id, output_file):
    """
    Artifact 다운로드 (새 서버 스펙)
    
    서버에서 presigned URL을 발급받아 S3에서 직접 다운로드합니다.
    """
    ctx = CLIContext()
    ctx.ensure_authenticated()

    click.echo(f"[+] Downloading artifact {artifact_id} to '{output_file}'...")
    
    success, result = ctx.client.download_artifact(artifact_id, output_file)
    
    if success:
        click.echo(click.style(f"✅ Artifact 다운로드 성공!", fg="green"))
        click.echo(f"   Saved to: {result}")
    else:
        click.echo(click.style(f"❌ 다운로드 실패: {result}", fg="red"))
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

