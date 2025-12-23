#!/usr/bin/env python3
"""
간단한 RAG 기능 테스트 스크립트
"""
import sys
sys.path.insert(0, '/home/wnsx0000/jhun/SeRVe/SeRVe-Client')

from vision_engine import VisionEngine

def test_embeddings_initialization():
    """Test 1: Embeddings 초기화 테스트"""
    print("=" * 60)
    print("Test 1: Embeddings 초기화")
    print("=" * 60)

    try:
        engine = VisionEngine()
        embeddings = engine._get_embeddings()
        print(f"✓ Embeddings 초기화 성공: {type(embeddings)}")
        print(f"  Model: {engine.embedding_model}")
        print(f"  Base URL: http://localhost:11434")
        return True
    except Exception as e:
        print(f"✗ Embeddings 초기화 실패: {str(e)}")
        return False

def test_vector_store_creation():
    """Test 2: Vector Store 생성 테스트"""
    print("\n" + "=" * 60)
    print("Test 2: Vector Store 생성")
    print("=" * 60)

    try:
        engine = VisionEngine()
        context = """This is a hydraulic valve (Type-K).
        Pressure limit: 500bar.
        Operating temperature: -20°C to +80°C.
        Material: Stainless steel 316L.
        Weight: 2.5 kg."""

        print("Context 내용:")
        print(f"  {context[:100]}...")

        print("\nVector Store 생성 중...")
        vectorstore = engine.create_vector_store(context)
        print(f"✓ Vector Store 생성 성공: {type(vectorstore)}")

        # Collection 정보 확인
        collection = vectorstore._collection
        print(f"  Collection 이름: {collection.name}")
        print(f"  문서 개수: {collection.count()}")

        return True
    except Exception as e:
        print(f"✗ Vector Store 생성 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_vector_extraction():
    """Test 3: Vector 추출 테스트"""
    print("\n" + "=" * 60)
    print("Test 3: Vector 추출")
    print("=" * 60)

    try:
        engine = VisionEngine()
        context = "This is a test document for vector extraction."

        # Vector store 생성
        vectorstore = engine.create_vector_store(context, chunk_size=50)

        # Vector 추출
        vectors = engine.extract_vectors(vectorstore)
        print(f"✓ Vector 추출 성공")
        print(f"  추출된 벡터 개수: {len(vectors['embeddings'])}")
        print(f"  문서 개수: {len(vectors['documents'])}")
        print(f"  첫 번째 문서: {vectors['documents'][0][:50]}...")

        return True
    except Exception as e:
        print(f"✗ Vector 추출 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_rag_chunking():
    """Test 4: RAG Chunking 테스트 (analyze_with_context 내부 로직)"""
    print("\n" + "=" * 60)
    print("Test 4: RAG Chunking")
    print("=" * 60)

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_core.documents import Document

        context = """This is a hydraulic valve (Type-K).
        Pressure limit: 500bar. Operating temperature: -20°C to +80°C.
        Material: Stainless steel 316L. Weight: 2.5 kg.
        Certification: ISO 9001, CE certified.
        Application: Industrial hydraulic systems."""

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=100,
            chunk_overlap=20,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        chunks = text_splitter.split_text(context)

        print(f"✓ Chunking 성공")
        print(f"  원본 길이: {len(context)} 문자")
        print(f"  생성된 청크 수: {len(chunks)}")
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i+1}: {chunk[:60]}...")

        return True
    except Exception as e:
        print(f"✗ Chunking 실패: {str(e)}")
        return False

def main():
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "RAG 구현 테스트 - VisionEngine" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = []

    # Test 1: Embeddings
    results.append(("Embeddings 초기화", test_embeddings_initialization()))

    # Test 2: Vector Store
    results.append(("Vector Store 생성", test_vector_store_creation()))

    # Test 3: Vector Extraction
    results.append(("Vector 추출", test_vector_extraction()))

    # Test 4: Chunking
    results.append(("RAG Chunking", test_rag_chunking()))

    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ 통과" if result else "✗ 실패"
        print(f"{status}: {test_name}")

    print(f"\n총 {passed}/{total} 테스트 통과")

    if passed == total:
        print("\n✓ 모든 테스트 성공! RAG 구현이 정상적으로 작동합니다.")
        return 0
    else:
        print(f"\n✗ {total - passed}개 테스트 실패. 로그를 확인하세요.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
