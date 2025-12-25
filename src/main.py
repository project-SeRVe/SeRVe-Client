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

# 환경 변수에서 설정 로드
CLOUD_URL = os.getenv("CLOUD_URL", "http://localhost:8080")
EDGE_EMAIL = os.getenv("EDGE_EMAIL", "edge@serve.local")
EDGE_PASSWORD = os.getenv("EDGE_PASSWORD", "edge123")
TEAM_ID = os.getenv("TEAM_ID", None)
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "./local_vectorstore")

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

    return StatusResponse(
        status="running",
        cloud_connected=cloud_connected,
        vectorstore_loaded=local_vectorstore is not None,
        team_id=TEAM_ID,
        uptime="N/A"  # 추후 업타임 추적 구현 가능
    )

@app.post("/api/sensor-data")
async def receive_sensor_data(sensor_data: SensorData, request: Request):
    """
    로봇으로부터 센서 데이터 수신

    처리 흐름:
    1. 로봇으로부터 JSON 데이터 수신
    2. vision_engine으로 처리 (선택적으로 로컬 벡터스토어 사용)
    3. serve_sdk로 암호화
    4. 클라우드에 청크로 업로드
    """
    client_ip = request.client.host
    logger.info(f"📥 센서 데이터 수신: {sensor_data.robot_id} (IP: {client_ip})")

    try:
        # 1. 데이터 검증 및 처리
        sensor_json = sensor_data.dict()
        sensor_str = json.dumps(sensor_json, indent=2, ensure_ascii=False)

        logger.info(f"   데이터: {sensor_str[:100]}...")

        # 2. 클라우드 연결 확인
        if not serve_client or not serve_client.session.is_authenticated():
            logger.warning("   ⚠ 클라우드 미연결, 로컬에만 저장")
            # TODO: 로컬 버퍼링 구현
            return {
                "status": "queued_local",
                "message": "클라우드 미연결, 데이터가 로컬에 대기 중",
                "robot_id": sensor_data.robot_id
            }

        # 3. TEAM_ID 확인
        if not TEAM_ID:
            logger.error("   ✗ TEAM_ID가 설정되지 않음")
            raise HTTPException(status_code=500, detail="TEAM_ID가 설정되지 않음")

        # 4. vision_engine으로 처리 (로컬 벡터스토어가 있는 경우)
        processed_data = sensor_str
        if local_vectorstore and vision_engine:
            try:
                # 로컬 벡터스토어에 추가 (향후 RAG 쿼리용)
                vision_engine.add_to_vector_store(
                    local_vectorstore,
                    sensor_str,
                    document_name=f"{sensor_data.robot_id}_{sensor_data.timestamp}"
                )
                logger.info("   ✓ 로컬 벡터스토어에 추가됨")
            except Exception as e:
                logger.warning(f"   ⚠ 벡터스토어 추가 실패: {e}")

        # 5. 클라우드에 업로드
        # 문서 이름 생성
        doc_name = f"{sensor_data.robot_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 문서 메타데이터 업로드
        success, msg = serve_client.upload_document(
            plaintext=f"Sensor data from {sensor_data.robot_id}",
            repo_id=TEAM_ID,
            file_name=doc_name,
            file_type="application/json"
        )

        if not success:
            logger.error(f"   ✗ 문서 생성 실패: {msg}")
            raise HTTPException(status_code=500, detail=f"문서 생성 실패: {msg}")

        logger.info(f"   ✓ 문서 생성됨: {doc_name}")

        # 문서 ID 조회 (최신 문서)
        docs, _ = serve_client.get_documents(TEAM_ID)
        if not docs or len(docs) == 0:
            logger.error("   ✗ 문서 ID 조회 실패")
            raise HTTPException(status_code=500, detail="문서 ID 조회 실패")

        latest_doc = docs[-1]
        doc_id = latest_doc.get('docId')

        # 단일 청크로 업로드
        chunks_data = [{
            "chunkIndex": 0,
            "data": processed_data
        }]

        success, msg = serve_client.upload_chunks_to_document(
            doc_id=doc_id,
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
            "doc_id": doc_id,
            "doc_name": doc_name
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
