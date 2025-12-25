#!/usr/bin/env python3
"""
청크 다운로드 테스트 스크립트
클라우드에 업로드된 청크를 다운로드하여 복호화 확인
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from serve_sdk import ServeClient
import json

# 설정
CLOUD_URL = "http://172.18.0.1:8080"  # WSL 환경: Docker 컨테이너에서 호스트 접근
EDGE_EMAIL = "edge@serve.local"
EDGE_PASSWORD = "edge123"
TEAM_ID = "b67b09a2-62ea-4b1e-a181-cfad8ed3517c"

def main():
    print("=" * 60)
    print("청크 다운로드 테스트")
    print("=" * 60)

    # 1. 클라이언트 생성 및 로그인
    client = ServeClient(server_url=CLOUD_URL)
    success, msg = client.login(EDGE_EMAIL, EDGE_PASSWORD)

    if not success:
        print(f"✗ 로그인 실패: {msg}")
        return

    print(f"✓ 로그인 성공: {EDGE_EMAIL}")

    # 2. 문서 목록 조회
    docs, msg = client.get_documents(TEAM_ID)

    if not docs:
        print(f"✗ 문서 조회 실패: {msg}")
        return

    print(f"✓ 총 {len(docs)}개 문서 조회됨")

    # 3. 최신 문서 3개 선택
    latest_docs = docs[-3:] if len(docs) >= 3 else docs

    print("\n최신 문서:")
    for i, doc in enumerate(latest_docs, 1):
        print(f"  {i}. {doc.get('originalFileName')} (ID: {doc.get('docId')[:8]}...)")

    # 4. 각 문서의 청크 다운로드 및 복호화
    print("\n" + "=" * 60)
    print("청크 다운로드 및 복호화 테스트")
    print("=" * 60)

    for i, doc in enumerate(latest_docs, 1):
        doc_id = doc.get('docId')
        file_name = doc.get('originalFileName')

        # originalFileName이 None이면 건너뛰기
        if not file_name:
            print(f"\n[{i}/{len(latest_docs)}] 문서 ID: {doc_id[:8]}... - 파일명 없음 (건너뛰기)")
            continue

        print(f"\n[{i}/{len(latest_docs)}] 문서: {file_name}")
        print(f"  문서 ID: {doc_id}")

        # 청크 다운로드 (fileName 사용)
        chunks, msg = client.download_chunks_from_document(file_name, TEAM_ID)

        if chunks is None:
            print(f"  ✗ 청크 다운로드 실패: {msg}")
            continue

        print(f"  ✓ {len(chunks)}개 청크 다운로드 성공")

        # 청크 내용 출력
        for chunk in chunks:
            chunk_idx = chunk.get('chunkIndex')
            data = chunk.get('data')
            version = chunk.get('version')

            print(f"    - 청크 #{chunk_idx} (버전: {version})")
            print(f"      데이터 크기: {len(data)} bytes")

            # JSON 파싱 시도
            try:
                json_data = json.loads(data)
                print(f"      내용: {json.dumps(json_data, indent=8, ensure_ascii=False)[:200]}...")
            except:
                print(f"      내용: {data[:100]}...")

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    main()
