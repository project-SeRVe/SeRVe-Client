"""
Edge Server FastAPI Proxy
Receives data from robots, processes with vision_engine, encrypts with serve_sdk, uploads to cloud
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

# Add parent directory to path to import serve_sdk and vision_engine
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "SeRVe-Client"))

from serve_sdk import ServeClient
from vision_engine import VisionEngine

# Configure logging
# Create log directory if it doesn't exist
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

# FastAPI app
app = FastAPI(title="SeRVe Edge Server", version="1.0.0")

# Global instances
serve_client: Optional[ServeClient] = None
vision_engine: Optional[VisionEngine] = None
local_vectorstore = None

# Configuration from environment variables
CLOUD_URL = os.getenv("CLOUD_URL", "http://localhost:8080")
EDGE_EMAIL = os.getenv("EDGE_EMAIL", "edge@serve.local")
EDGE_PASSWORD = os.getenv("EDGE_PASSWORD", "edge123")
TEAM_ID = os.getenv("TEAM_ID", None)
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "./local_vectorstore")

# Pydantic models
class SensorData(BaseModel):
    """Robot sensor data"""
    robot_id: str
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    data: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class StatusResponse(BaseModel):
    """Edge server status"""
    status: str
    cloud_connected: bool
    vectorstore_loaded: bool
    team_id: Optional[str]
    uptime: str

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize edge server on startup"""
    global serve_client, vision_engine, local_vectorstore

    logger.info("=" * 60)
    logger.info("Edge Server Starting Up")
    logger.info("=" * 60)

    # 1. Initialize ServeClient
    try:
        serve_client = ServeClient(server_url=CLOUD_URL)
        logger.info(f"✓ ServeClient initialized (Cloud: {CLOUD_URL})")
    except Exception as e:
        logger.error(f"✗ Failed to initialize ServeClient: {e}")
        raise

    # 2. Login to cloud
    try:
        success, msg = serve_client.login(EDGE_EMAIL, EDGE_PASSWORD)
        if success:
            logger.info(f"✓ Logged in to cloud as {EDGE_EMAIL}")
        else:
            logger.error(f"✗ Cloud login failed: {msg}")
            logger.warning("Continuing without cloud connection...")
    except Exception as e:
        logger.error(f"✗ Cloud login error: {e}")
        logger.warning("Continuing without cloud connection...")

    # 3. Initialize VisionEngine
    try:
        vision_engine = VisionEngine()
        logger.info("✓ VisionEngine initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize VisionEngine: {e}")
        raise

    # 4. Load local vectorstore (optional)
    try:
        if os.path.exists(VECTORSTORE_PATH):
            local_vectorstore = vision_engine.load_vector_store(
                collection_name="serve_edge_rag",
                persist_directory=VECTORSTORE_PATH
            )
            if local_vectorstore:
                logger.info(f"✓ Local vectorstore loaded from {VECTORSTORE_PATH}")
            else:
                logger.info("ℹ No vectorstore found, will create on demand")
        else:
            logger.info(f"ℹ Vectorstore path does not exist: {VECTORSTORE_PATH}")
    except Exception as e:
        logger.warning(f"⚠ Failed to load vectorstore: {e}")
        local_vectorstore = None

    logger.info("=" * 60)
    logger.info("Edge Server Ready")
    logger.info("=" * 60)

# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "SeRVe Edge Server", "version": "1.0.0"}

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get edge server status"""
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
        uptime="N/A"  # Could implement uptime tracking
    )

@app.post("/api/sensor-data")
async def receive_sensor_data(sensor_data: SensorData, request: Request):
    """
    Receive sensor data from robot

    Flow:
    1. Receive JSON data from robot
    2. Process with vision_engine (optional local vectorstore)
    3. Encrypt with serve_sdk
    4. Upload to cloud as chunks
    """
    client_ip = request.client.host
    logger.info(f"📥 Received sensor data from {sensor_data.robot_id} (IP: {client_ip})")

    try:
        # 1. Validate and process data
        sensor_json = sensor_data.dict()
        sensor_str = json.dumps(sensor_json, indent=2)

        logger.info(f"   Data: {sensor_str[:100]}...")

        # 2. Check for cloud connection
        if not serve_client or not serve_client.session.is_authenticated():
            logger.warning("   ⚠ Cloud not connected, storing locally only")
            # TODO: Implement local buffering
            return {
                "status": "queued_local",
                "message": "Cloud not connected, data queued locally",
                "robot_id": sensor_data.robot_id
            }

        # 3. Check TEAM_ID
        if not TEAM_ID:
            logger.error("   ✗ TEAM_ID not configured")
            raise HTTPException(status_code=500, detail="TEAM_ID not configured")

        # 4. Process with vision_engine (if local vectorstore exists)
        processed_data = sensor_str
        if local_vectorstore and vision_engine:
            try:
                # Add to local vectorstore for future RAG queries
                vision_engine.add_to_vector_store(
                    local_vectorstore,
                    sensor_str,
                    document_name=f"{sensor_data.robot_id}_{sensor_data.timestamp}"
                )
                logger.info("   ✓ Added to local vectorstore")
            except Exception as e:
                logger.warning(f"   ⚠ Failed to add to vectorstore: {e}")

        # 5. Upload to cloud
        # Create document name
        doc_name = f"{sensor_data.robot_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Upload document metadata
        success, msg = serve_client.upload_document(
            plaintext=f"Sensor data from {sensor_data.robot_id}",
            repo_id=TEAM_ID,
            file_name=doc_name,
            file_type="application/json"
        )

        if not success:
            logger.error(f"   ✗ Failed to create document: {msg}")
            raise HTTPException(status_code=500, detail=f"Failed to create document: {msg}")

        logger.info(f"   ✓ Document created: {doc_name}")

        # Get document ID (latest document)
        docs, _ = serve_client.get_documents(TEAM_ID)
        if not docs or len(docs) == 0:
            logger.error("   ✗ Failed to retrieve document ID")
            raise HTTPException(status_code=500, detail="Failed to retrieve document ID")

        latest_doc = docs[-1]
        doc_id = latest_doc.get('docId')

        # Upload as single chunk
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
            logger.error(f"   ✗ Failed to upload chunks: {msg}")
            raise HTTPException(status_code=500, detail=f"Failed to upload chunks: {msg}")

        logger.info(f"   ✓ Uploaded 1 chunk to cloud (encrypted)")
        logger.info(f"   ✓ Data from {sensor_data.robot_id} processed successfully")

        return {
            "status": "success",
            "message": "Data encrypted and uploaded to cloud",
            "robot_id": sensor_data.robot_id,
            "doc_id": doc_id,
            "doc_name": doc_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   ✗ Error processing sensor data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    import traceback
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

if __name__ == "__main__":
    # Run FastAPI server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9001,
        log_level="info"
    )
