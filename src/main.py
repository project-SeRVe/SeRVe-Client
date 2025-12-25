#!/usr/bin/env python3
"""
Edge Server FastAPI Proxy
로봇으로부터 센서 데이터를 받아서 vision_engine으로 처리하고,
serve_sdk로 암호화한 후 클라우드로 업로드하는 프록시 서버
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# 상위 디렉터리를 경로에 추가하여 serve_sdk import
sys.path.insert(0, str(Path(__file__).parent.parent))

from serve_sdk import ServeClient
from vision_engine import VisionEngine

# 로깅 설정
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'edge-server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="SeRVe Edge Server", version="1.0.0")

# 전역 인스턴스
serve_client: Optional[ServeClient] = None
vision_engine: Optional[VisionEngine] = None
local_vectorstore = None
last_sync_version: int = 0  # 마지막 동기화 버전

# 환경 변수에서 설정 로드
CLOUD_URL = os.getenv("CLOUD_URL", "http://localhost:8080")
EDGE_EMAIL = os.getenv("EDGE_EMAIL", "edge@serve.local")
EDGE_PASSWORD = os.getenv("EDGE_PASSWORD", "edge123")
TEAM_ID = os.getenv("TEAM_ID", None)
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "./local_vectorstore")
SYNC_VERSION_FILE = os.getenv("SYNC_VERSION_FILE", "./sync_version.txt")
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "30"))  # 동기화 주기 (초)

# Pydantic 모델 정의
class SensorData(BaseModel):
    """로봇 센서 데이터 모델"""
    robot_id: str
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    data: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class StatusResponse(BaseModel):
    """Edge 서버 상태 응답 모델"""
    status: str
    cloud_connected: bool
    vectorstore_loaded: bool
    team_id: Optional[str]
    uptime: str
    sync_enabled: bool
    last_sync_version: int

# ==================== 동기화 유틸리티 ====================

def load_sync_version() -> int:
    """마지막 동기화 버전 로드"""
    try:
        if os.path.exists(SYNC_VERSION_FILE):
            with open(SYNC_VERSION_FILE, 'r') as f:
                version = int(f.read().strip())
                logger.info(f"동기화 버전 로드: {version}")
                return version
    except Exception as e:
        logger.warning(f"동기화 버전 로드 실패: {e}")
    return 0

def save_sync_version(version: int):
    """동기화 버전 저장"""
    try:
        with open(SYNC_VERSION_FILE, 'w') as f:
            f.write(str(version))
        logger.debug(f"동기화 버전 저장: {version}")
    except Exception as e:
        logger.error(f"동기화 버전 저장 실패: {e}")

import asyncio

async def background_sync_worker():
    """
    백그라운드 청크 동기화 워커
    주기적으로 클라우드와 증분 동기화를 수행하여 로컬 벡터스토어를 최신 상태로 유지
    """
    global last_sync_version, local_vectorstore

    logger.info("=" * 60)
    logger.info(f"🔄 백그라운드 동기화 워커 시작 (주기: {SYNC_INTERVAL}초)")
    logger.info("=" * 60)

    # 동기화 버전 로드
    last_sync_version = load_sync_version()

    while True:
        try:
            # 동기화 주기 대기
            await asyncio.sleep(SYNC_INTERVAL)

            # 클라우드 연결 확인
            if not serve_client or not serve_client.session.is_authenticated():
                logger.debug("동기화 건너뜀: 클라우드 미연결")
                continue

            # TEAM_ID 확인
            if not TEAM_ID:
                logger.debug("동기화 건너뜀: TEAM_ID 미설정")
                continue

            logger.info(f"📥 증분 동기화 시작 (lastVersion={last_sync_version})...")

            # 증분 동기화 실행
            documents_chunks, msg = serve_client.sync_team_chunks(TEAM_ID, last_sync_version)

            if not documents_chunks:
                logger.info("   변경사항 없음")
                continue

            logger.info(f"   {msg}")

            # 로컬 벡터스토어에 반영
            total_synced = 0
            max_version = last_sync_version

            for doc_id, chunks in documents_chunks.items():
                for chunk in chunks:
                    chunk_version = chunk['version']
                    chunk_index = chunk['chunkIndex']
                    is_deleted = chunk['isDeleted']

                    if is_deleted:
                        logger.info(f"   삭제된 청크: doc={doc_id[:8]}... chunk={chunk_index} (v{chunk_version})")
                        # TODO: 로컬 벡터스토어에서 삭제 (현재 ChromaDB는 문서 단위 삭제만 지원)
                    else:
                        # 로컬 벡터스토어에 추가/업데이트
                        data = chunk['data']
                        doc_name = f"{doc_id}_chunk_{chunk_index}"

                        if vision_engine:
                            if local_vectorstore:
                                vision_engine.add_to_vector_store(
                                    local_vectorstore,
                                    data,
                                    document_name=doc_name
                                )
                            else:
                                # 벡터스토어가 없으면 생성
                                logger.info(f"   로컬 벡터스토어 생성 (첫 동기화)")
                                local_vectorstore = vision_engine.create_vector_store(
                                    data,
                                    collection_name="serve_edge_rag",
                                    persist_directory=VECTORSTORE_PATH,
                                    document_name=doc_name
                                )

                            logger.info(f"   ✓ 청크 동기화: {doc_name} (v{chunk_version})")
                            total_synced += 1

                    # 최신 버전 추적
                    if chunk_version > max_version:
                        max_version = chunk_version

            # 동기화 버전 업데이트 및 저장
            if max_version > last_sync_version:
                last_sync_version = max_version
                save_sync_version(last_sync_version)
                logger.info(f"   최신 버전 업데이트: {last_sync_version} ({total_synced}개 청크 동기화 완료)")

        except Exception as e:
            logger.error(f"동기화 워커 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())

# 서버 시작 이벤트
@app.on_event("startup")
async def startup_event():
    """Edge 서버 초기화"""
    global serve_client, vision_engine, local_vectorstore

    logger.info("=" * 60)
    logger.info("Edge Server 시작 중...")
    logger.info("=" * 60)

    # 1. ServeClient 초기화
    try:
        serve_client = ServeClient(server_url=CLOUD_URL)
        logger.info(f"✓ ServeClient 초기화 완료 (Cloud: {CLOUD_URL})")
    except Exception as e:
        logger.error(f"✗ ServeClient 초기화 실패: {e}")
        raise

    # 2. 클라우드 로그인
    try:
        success, msg = serve_client.login(EDGE_EMAIL, EDGE_PASSWORD)
        if success:
            logger.info(f"✓ 클라우드 로그인 성공: {EDGE_EMAIL}")
        else:
            logger.error(f"✗ 클라우드 로그인 실패: {msg}")
            logger.warning("클라우드 연결 없이 계속 진행...")
    except Exception as e:
        logger.error(f"✗ 클라우드 로그인 오류: {e}")
        logger.warning("클라우드 연결 없이 계속 진행...")

    # 3. VisionEngine 초기화
    try:
        vision_engine = VisionEngine()
        logger.info("✓ VisionEngine 초기화 완료")
    except Exception as e:
        logger.error(f"✗ VisionEngine 초기화 실패: {e}")
        raise

    # 4. 로컬 벡터스토어 로드 (선택사항)
    try:
        if os.path.exists(VECTORSTORE_PATH):
            local_vectorstore = vision_engine.load_vector_store(
                collection_name="serve_edge_rag",
                persist_directory=VECTORSTORE_PATH
            )
            if local_vectorstore:
                logger.info(f"✓ 로컬 벡터스토어 로드 완료: {VECTORSTORE_PATH}")
            else:
                logger.info("ℹ 벡터스토어를 찾을 수 없음, 필요시 생성됨")
        else:
            logger.info(f"ℹ 벡터스토어 경로가 존재하지 않음: {VECTORSTORE_PATH}")
    except Exception as e:
        logger.warning(f"⚠ 벡터스토어 로드 실패: {e}")
        local_vectorstore = None

    # 5. 백그라운드 동기화 워커 시작
    if TEAM_ID and serve_client and serve_client.session.is_authenticated():
        asyncio.create_task(background_sync_worker())
        logger.info("✓ 백그라운드 동기화 워커 시작됨")
    else:
        logger.warning("⚠ 동기화 워커 시작 실패: TEAM_ID 미설정 또는 클라우드 미연결")

    logger.info("=" * 60)
    logger.info("Edge Server 준비 완료")
    logger.info("=" * 60)

# Health check 엔드포인트
@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {"message": "SeRVe Edge Server", "version": "1.0.0"}

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Edge 서버 상태 조회"""
    cloud_connected = False
    if serve_client:
        try:
            cloud_connected = serve_client.session.is_authenticated()
        except:
            pass

    sync_enabled = bool(TEAM_ID and cloud_connected)

    return StatusResponse(
        status="running",
        cloud_connected=cloud_connected,
        vectorstore_loaded=local_vectorstore is not None,
        team_id=TEAM_ID,
        uptime="N/A",  # 추후 업타임 추적 구현 가능
        sync_enabled=sync_enabled,
        last_sync_version=last_sync_version
    )

@app.post("/api/sensor-data")
async def receive_sensor_data(sensor_data: SensorData, request: Request):
    """
    로봇으로부터 센서 데이터 수신
    [수정됨] 최초 실행 시 벡터스토어가 없으면 생성하도록 로직 개선
    """
    # 전역 변수 수정을 위해 global 선언 필수
    global local_vectorstore 

    client_ip = request.client.host
    logger.info(f"📥 센서 데이터 수신: {sensor_data.robot_id} (IP: {client_ip})")

    try:
        # 1. 데이터 검증 및 처리
        sensor_json = sensor_data.dict()
        sensor_str = json.dumps(sensor_json, indent=2, ensure_ascii=False)

        logger.info(f"   데이터: {sensor_str[:100]}...")

        # 2. 클라우드 연결 확인 (기존 코드 유지)
        if not serve_client or not serve_client.session.is_authenticated():
            logger.warning("   ⚠ 클라우드 미연결, 로컬에만 저장 시도")
            # 여기서도 로컬 저장은 시도해야 함 (아래 로직으로 통과)

        # 3. TEAM_ID 확인 (기존 코드 유지)
        if not TEAM_ID:
            logger.error("   ✗ TEAM_ID가 설정되지 않음")
            # TEAM_ID 없어도 로컬 저장은 되게 할지, 에러 낼지 결정 필요. 일단 기존 유지.
            raise HTTPException(status_code=500, detail="TEAM_ID가 설정되지 않음")

        # ==================================================================
        # [핵심 수정 구간] 4. vision_engine으로 처리 및 저장
        # ==================================================================
        if vision_engine:
            doc_name = f"{sensor_data.robot_id}_{sensor_data.timestamp}"
            
            try:
                if local_vectorstore:
                    # A. 이미 스토어가 있으면 -> 추가 (Add)
                    vision_engine.add_to_vector_store(
                        local_vectorstore,
                        sensor_str,
                        document_name=doc_name
                    )
                    logger.info("   ✓ 로컬 벡터스토어에 데이터 추가됨 (Append)")
                else:
                    # B. 스토어가 없으면(최초 실행) -> 생성 (Create)
                    logger.info(f"   ℹ 로컬 벡터스토어 없음. 신규 생성 시작... ({VECTORSTORE_PATH})")
                    local_vectorstore = vision_engine.create_vector_store(
                        sensor_str,
                        collection_name="serve_edge_rag",
                        persist_directory=VECTORSTORE_PATH,
                        document_name=doc_name
                    )
                    logger.info("   ✓ 로컬 벡터스토어 생성 및 첫 데이터 저장 완료 (Create)")
            except Exception as e:
                logger.warning(f"   ⚠ 벡터스토어 처리 실패: {e}")
                # 디버깅을 위해 상세 로그 출력
                import traceback
                logger.warning(traceback.format_exc())

        # 5. 클라우드에 청크 업로드 (신규: 문서 생성 없이 바로 청크 업로드)
        doc_name_cloud = f"{sensor_data.robot_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        chunks_data = [{
            "chunkIndex": 0,
            "data": sensor_str
        }]

        success, msg = serve_client.upload_chunks_to_document(
            file_name=doc_name_cloud,
            repo_id=TEAM_ID,
            chunks_data=chunks_data
        )

        if not success:
            logger.error(f"   ✗ 청크 업로드 실패: {msg}")
            raise HTTPException(status_code=500, detail=f"청크 업로드 실패: {msg}")

        logger.info(f"   ✓ 1개 청크가 클라우드에 업로드됨 (암호화)")
        logger.info(f"   ✓ {sensor_data.robot_id}의 데이터 처리 완료")

        return {
            "status": "success",
            "message": "데이터가 암호화되어 클라우드에 업로드됨",
            "robot_id": sensor_data.robot_id,
            "file_name": doc_name_cloud
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ✗ 센서 데이터 처리 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# 전역 예외 핸들러
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """전역 예외 핸들러"""
    logger.error(f"처리되지 않은 예외: {exc}")
    import traceback
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "내부 서버 오류", "error": str(exc)}
    )

if __name__ == "__main__":
    # FastAPI 서버 실행
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9001,
        log_level="info"
    )
