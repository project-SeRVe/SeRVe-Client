#!/usr/bin/env python3
"""
멀티모달 RAG 기능 테스트
- CLIP 임베딩을 사용한 이미지 저장
- 이미지 유사도 검색
- 멀티모달 RAG 분석
"""

import sys
import os

# src 디렉터리를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vision_engine import VisionEngine
from PIL import Image
import shutil

def test_multimodal_rag():
    """멀티모달 RAG 기능 테스트"""

    print("=" * 60)
    print("멀티모달 RAG 기능 테스트")
    print("=" * 60)

    # 1. VisionEngine 초기화 (멀티모달 모드)
    print("\n[1] VisionEngine 초기화 (use_multimodal=True)...")
    vision = VisionEngine(use_multimodal=True)
    print("✓ 멀티모달 모드로 초기화 완료")

    # 2. 테스트용 벡터스토어 디렉터리 정리
    test_vectorstore_dir = "./test_multimodal_vectorstore"
    if os.path.exists(test_vectorstore_dir):
        print(f"\n[2] 기존 테스트 벡터스토어 삭제 중: {test_vectorstore_dir}")
        shutil.rmtree(test_vectorstore_dir)
        print("✓ 삭제 완료")

    # 3. 첫 번째 이미지로 벡터스토어 생성
    print("\n[3] 첫 번째 이미지로 벡터스토어 생성 중...")
    image_files = [
        "rag_images/2c412ad3-38df-407c-b5e4-58b1f402528b.jpg",
        "rag_images/54e24853-0737-4bb6-bc90-713dcd56e277.jpg",
        "rag_images/7aa5e05d-db59-4e74-bf23-6cb8cb23469a.jpg",
        "rag_images/efb40409-fe7f-43ee-ae96-410b37b27bfa.jpg"
    ]

    # 이미지 파일 존재 확인
    existing_images = [img for img in image_files if os.path.exists(img)]
    if not existing_images:
        print("❌ 오류: rag_images/ 디렉터리에 이미지가 없습니다.")
        return False

    print(f"   발견된 이미지: {len(existing_images)}개")

    # 첫 번째 이미지로 벡터스토어 생성
    first_image = Image.open(existing_images[0])
    vectorstore = vision.create_vector_store_with_image(
        image=first_image,
        caption="첫 번째 테스트 이미지",
        collection_name="multimodal_test",
        persist_directory=test_vectorstore_dir,
        document_name="Test Images"
    )
    print(f"✓ 벡터스토어 생성 완료: {existing_images[0]}")

    # 4. 나머지 이미지들 추가
    print("\n[4] 나머지 이미지들을 벡터스토어에 추가 중...")
    for i, img_path in enumerate(existing_images[1:], start=2):
        image = Image.open(img_path)
        vectorstore = vision.add_image_to_vector_store(
            vectorstore=vectorstore,
            image=image,
            caption=f"{i}번째 테스트 이미지",
            document_name="Test Images"
        )
        print(f"   ✓ 이미지 추가 완료: {img_path}")

    # 5. 벡터스토어 정보 확인
    print("\n[5] 벡터스토어 정보 확인...")
    vectors = vision.extract_vectors(vectorstore)
    print(f"   총 저장된 항목 수: {len(vectors['ids'])}개")
    print(f"   임베딩 차원: {len(vectors['embeddings'][0]) if len(vectors['embeddings']) > 0 else 'N/A'}차원")

    # 메타데이터 확인
    image_count = sum(1 for meta in vectors['metadatas'] if meta.get('modality') == 'image')
    print(f"   이미지 항목: {image_count}개")

    # 6. 이미지 유사도 검색 테스트
    print("\n[6] 이미지 유사도 검색 테스트...")
    query_image = Image.open(existing_images[0])
    similar_images = vision.similarity_search_by_image(
        input_image=query_image,
        vectorstore=vectorstore,
        k=3,
        modality_filter="image"
    )

    print(f"   검색된 유사 이미지: {len(similar_images)}개")
    for i, doc in enumerate(similar_images, start=1):
        caption = doc.metadata.get('caption', 'N/A')
        image_path = doc.metadata.get('image_path', 'N/A')
        print(f"   {i}. 캡션: {caption}")
        print(f"      경로: {image_path}")

    # 7. 정리
    print("\n[7] 테스트 벡터스토어 정리 중...")
    if os.path.exists(test_vectorstore_dir):
        shutil.rmtree(test_vectorstore_dir)
        print("✓ 정리 완료")

    print("\n" + "=" * 60)
    print("✅ 모든 멀티모달 RAG 테스트 통과!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = test_multimodal_rag()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
