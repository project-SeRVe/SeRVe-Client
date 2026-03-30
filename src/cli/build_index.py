"""
Build local FAISS vector index from processed_demo.npz files.

VLA 서버(ricl_openpi_libero)와 동일한 방식으로 FAISS 인덱스를 구축합니다.
- embedding key: top_image_embeddings (VLA 서버와 동일)
- 거리: L2
- 저장 위치: ~/.serve/faiss/<team_id>/

저장 구조:
    ~/.serve/faiss/<team_id>/
        index.faiss      ← FAISS 인덱스 파일
        metadata.npz     ← episode/step 메타데이터 (검색 결과 역참조용)
"""
import json
import logging
from pathlib import Path
from typing import List, Optional

import click
import numpy as np

logger = logging.getLogger(__name__)

# VLA 서버와 동일하게 top_image_embeddings 사용
DEFAULT_EMBEDDING_KEY = "top_image_embeddings"


def find_npz_files(root: Path) -> List[Path]:
    """Find all processed_demo.npz files under root directory."""
    return sorted(root.rglob("processed_demo.npz"))


def to_prompt(value) -> str:
    """Extract prompt string from NPZ value."""
    if isinstance(value, np.ndarray):
        if value.shape == ():
            value = value.item()
        elif value.size == 1:
            value = value.reshape(()).item()
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        return ""
    return value


def peek_npz_meta(npz_path: Path) -> dict:
    """NPZ 파일에서 메타데이터만 빠르게 읽어 반환."""
    try:
        data = np.load(npz_path, allow_pickle=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    result = {"ok": True}
    result["prompt"] = to_prompt(data["prompt"]) if "prompt" in data.files else ""

    if "state" in data.files and np.asarray(data["state"]).ndim == 2:
        arr = np.asarray(data["state"])
        result["num_steps"] = arr.shape[0]
        result["state_dim"] = arr.shape[1]
    else:
        result["num_steps"] = None
        result["state_dim"] = None

    if "actions" in data.files and np.asarray(data["actions"]).ndim == 2:
        result["action_dim"] = np.asarray(data["actions"]).shape[1]
    else:
        result["action_dim"] = None

    emb_key = DEFAULT_EMBEDDING_KEY
    # fallback to base_image_embeddings if top_image_embeddings not present
    if emb_key not in data.files:
        emb_key = "base_image_embeddings"
    if emb_key in data.files:
        emb = np.asarray(data[emb_key])
        result["embed_dim"] = emb.shape[1] if emb.ndim == 2 else None
    else:
        result["embed_dim"] = None

    return result


def interactive_select(npz_files: List[Path], root: Path) -> List[Path]:
    """각 NPZ 파일의 메타데이터를 보여주고 y/n/q 로 선택하게 함."""
    selected = []
    total = len(npz_files)

    click.echo("")
    click.echo("=" * 60)
    click.echo(f"  데모 선택 모드 ({total}개 발견)")
    click.echo("  [y] 포함  [n] 건너뜀  [q] 선택 완료")
    click.echo("=" * 60)

    for idx, npz_path in enumerate(npz_files, 1):
        try:
            rel = str(npz_path.relative_to(root))
        except ValueError:
            rel = str(npz_path)

        meta = peek_npz_meta(npz_path)

        click.echo(f"\n[{idx}/{total}] {rel}")
        if not meta["ok"]:
            click.echo(click.style(f"  ⚠ 읽기 실패: {meta.get('error')}", fg="yellow"))
        else:
            prompt_display = meta["prompt"] or "(prompt 없음)"
            if len(prompt_display) > 70:
                prompt_display = prompt_display[:67] + "..."
            click.echo(f"  Prompt  : {prompt_display}")
            click.echo(f"  Steps   : {meta['num_steps']}")
            click.echo(f"  State   : {meta['state_dim']}  Action: {meta['action_dim']}")
            click.echo(f"  EmbedDim: {meta['embed_dim']}")

        while True:
            choice = click.prompt("  선택", type=str, default="y").strip().lower()
            if choice in ("y", "n", "q"):
                break
            click.echo(click.style("  y / n / q 중 하나를 입력하세요.", fg="red"))

        if choice == "y":
            selected.append(npz_path)
            click.echo(click.style("  ✓ 선택됨", fg="green"))
        elif choice == "n":
            click.echo(click.style("  - 건너뜀", fg="yellow"))
        elif choice == "q":
            click.echo(click.style("  선택 완료 (나머지 건너뜀)", fg="cyan"))
            break

    click.echo("")
    click.echo(f"선택된 데모: {len(selected)} / {total}")
    return selected


@click.command(name='build-index')
@click.argument('team-id')
@click.option('--from-dir', 'from_dir', type=click.Path(), default=None,
              help='NPZ 파일을 검색할 루트 디렉토리 (기본값: ~/.serve/demos/)')
@click.option('--select', 'interactive', is_flag=True,
              help='인터랙티브 선택 모드: 각 데모를 보고 포함 여부 결정')
@click.option('--overwrite', is_flag=True, help='기존 FAISS 인덱스 덮어쓰기')
@click.option('--embedding-key', default=DEFAULT_EMBEDDING_KEY,
              help=f'사용할 임베딩 키 (기본값: {DEFAULT_EMBEDDING_KEY})')
def build_index_command(
    team_id: str,
    from_dir: Optional[str],
    interactive: bool,
    overwrite: bool,
    embedding_key: str,
):
    """
    로컬 디렉토리의 processed_demo.npz 파일로 FAISS 벡터 인덱스를 구축합니다.

    VLA 서버(ricl_openpi_libero)와 동일한 FAISS(L2) 방식을 사용합니다.

    TEAM_ID: 인덱스 저장 디렉토리 식별자

    \b
    기본 스캔 경로: ~/.serve/demos/
    출력: ~/.serve/faiss/<team_id>/index.faiss + metadata.npz

    \b
    Examples:
        # 전체 자동 인덱싱
        serve data build-index my-team-id

        # 인터랙티브 선택 모드
        serve data build-index my-team-id --select

        # 커스텀 디렉토리
        serve data build-index my-team-id --from-dir ./test_demos/ --select

        # 기존 인덱스 재구축
        serve data build-index my-team-id --overwrite
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    try:
        import faiss
    except ImportError:
        click.echo(click.style("❌ faiss-cpu가 설치되지 않았습니다.", fg="red"))
        click.echo("설치: pip install faiss-cpu")
        raise click.Abort()

    # Determine root directory
    root = Path(from_dir).resolve() if from_dir else Path.home() / ".serve" / "demos"

    if not root.exists():
        click.echo(click.style(f"❌ 디렉토리가 존재하지 않습니다: {root}", fg="red"))
        click.echo("먼저 파일을 업로드하거나 다운로드하세요.")
        raise click.Abort()

    npz_files = find_npz_files(root)
    if not npz_files:
        click.echo(click.style(f"❌ processed_demo.npz 파일을 찾을 수 없습니다: {root}", fg="red"))
        raise click.Abort()

    click.echo(f"[+] {len(npz_files)}개의 processed_demo.npz 파일 발견: {root}")

    # Interactive selection
    if interactive:
        npz_files = interactive_select(npz_files, root)
        if not npz_files:
            click.echo(click.style("선택된 데모가 없습니다. 종료합니다.", fg="yellow"))
            return
    else:
        click.echo(f"    → 전체 {len(npz_files)}개 인덱싱")

    click.echo(f"[+] Embedding key: {embedding_key}")
    click.echo("")

    # Output directory
    faiss_dir = Path.home() / ".serve" / "faiss" / team_id
    if faiss_dir.exists() and not overwrite:
        click.echo(click.style(f"❌ FAISS 인덱스가 이미 존재합니다: {faiss_dir}", fg="red"))
        click.echo("재구축하려면 --overwrite 옵션을 사용하세요.")
        raise click.Abort()

    faiss_dir.mkdir(parents=True, exist_ok=True)

    # Collect embeddings and metadata
    all_embeddings = []
    # metadata: (episode_idx, step_idx, npz_path, prompt, num_steps, state_dim, action_dim)
    all_meta_episode = []
    all_meta_step = []
    all_meta_path = []
    all_meta_prompt = []
    all_meta_num_steps = []
    all_meta_state_dim = []
    all_meta_action_dim = []
    all_meta_relative = []

    episodes_processed = 0
    embedding_dim = None

    with click.progressbar(enumerate(npz_files), length=len(npz_files),
                           label="Processing NPZ files") as bar:
        for episode_idx, npz_path in bar:
            # Try primary embedding key, fallback to base_image_embeddings
            try:
                data = np.load(npz_path, allow_pickle=True)
            except Exception as exc:
                click.echo(click.style(f"\n✗ 로드 실패 {npz_path}: {exc}", fg="red"))
                continue

            actual_key = embedding_key
            if actual_key not in data.files:
                actual_key = "base_image_embeddings"
                if actual_key not in data.files:
                    click.echo(click.style(f"\n✗ 임베딩 키 없음: {npz_path}", fg="red"))
                    continue

            emb = np.asarray(data[actual_key], dtype=np.float32)
            if emb.ndim != 2:
                click.echo(click.style(f"\n✗ 잘못된 임베딩 shape {emb.shape}: {npz_path}", fg="red"))
                continue

            num_steps_actual = emb.shape[0]
            if embedding_dim is None:
                embedding_dim = emb.shape[1]
            elif embedding_dim != emb.shape[1]:
                click.echo(click.style(
                    f"\n✗ 임베딩 차원 불일치 (expected {embedding_dim}, got {emb.shape[1]}): {npz_path}",
                    fg="red"
                ))
                continue

            prompt = to_prompt(data["prompt"]) if "prompt" in data.files else ""
            state_dim = int(data["state"].shape[1]) if "state" in data.files and np.asarray(data["state"]).ndim == 2 else -1
            action_dim = int(data["actions"].shape[1]) if "actions" in data.files and np.asarray(data["actions"]).ndim == 2 else -1

            try:
                relative_path = str(npz_path.relative_to(root))
            except ValueError:
                relative_path = str(npz_path)

            all_embeddings.append(emb)
            for step_idx in range(num_steps_actual):
                all_meta_episode.append(episode_idx)
                all_meta_step.append(step_idx)
                all_meta_path.append(str(npz_path))
                all_meta_relative.append(relative_path)
                all_meta_prompt.append(prompt)
                all_meta_num_steps.append(num_steps_actual)
                all_meta_state_dim.append(state_dim)
                all_meta_action_dim.append(action_dim)

            episodes_processed += 1

    if not all_embeddings:
        click.echo(click.style("❌ 유효한 임베딩을 찾을 수 없습니다.", fg="red"))
        raise click.Abort()

    # Stack all embeddings
    embeddings_matrix = np.concatenate(all_embeddings, axis=0).astype(np.float32)
    total_vectors = embeddings_matrix.shape[0]

    click.echo("")
    click.echo(f"Collected {total_vectors} vectors from {episodes_processed} episode(s)")
    click.echo(f"Embedding dimension: {embedding_dim}")

    # Build FAISS index (L2, same as VLA server)
    click.echo("\n[+] Building FAISS index (L2)...")
    index = faiss.IndexFlatL2(embedding_dim)
    index.add(embeddings_matrix)

    # Save FAISS index
    index_path = faiss_dir / "index.faiss"
    faiss.write_index(index, str(index_path))
    click.echo(f"    Saved: {index_path}")

    # Save metadata
    meta_path = faiss_dir / "metadata.npz"
    np.savez(
        meta_path,
        episode_idx=np.array(all_meta_episode, dtype=np.int32),
        step_idx=np.array(all_meta_step, dtype=np.int32),
        num_steps=np.array(all_meta_num_steps, dtype=np.int32),
        state_dim=np.array(all_meta_state_dim, dtype=np.int32),
        action_dim=np.array(all_meta_action_dim, dtype=np.int32),
        npz_path=np.array(all_meta_path),
        relative_path=np.array(all_meta_relative),
        prompt=np.array(all_meta_prompt),
    )
    click.echo(f"    Saved: {meta_path}")

    # Save index info
    info = {
        "team_id": team_id,
        "embedding_key": embedding_key,
        "embedding_dim": embedding_dim,
        "num_vectors": total_vectors,
        "num_episodes": episodes_processed,
        "source_dir": str(root),
        "metric": "L2",
    }
    info_path = faiss_dir / "index_info.json"
    info_path.write_text(json.dumps(info, indent=2))

    click.echo("")
    click.echo(click.style("✓ FAISS 벡터 인덱스 구축 완료!", fg="green", bold=True))
    click.echo(f"  Location   : {faiss_dir}")
    click.echo(f"  Source dir : {root}")
    click.echo(f"  Vectors    : {total_vectors}")
    click.echo(f"  Episodes   : {episodes_processed}")
    click.echo(f"  Embed dim  : {embedding_dim}")
    click.echo(f"  Metric     : L2 (VLA 서버와 동일)")
