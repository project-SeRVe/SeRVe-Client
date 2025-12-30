#!/usr/bin/env python3
"""
로봇 시뮬레이터
Edge 서버로 센서 데이터 전송 (정상 모드 또는 공격 모드)
"""

import time
import argparse
import random
import json
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 로봇 설정
ROBOT_ID = "AGV-001"
EDGE_SERVER_URL = "http://localhost:9000/api/sensor-data"
CLOUD_SERVER_URL = os.getenv("CLOUD_URL", "http://localhost:8080")
EDGE_EMAIL = os.getenv("EDGE_EMAIL", "edge1@serve.local")
EDGE_PASSWORD = os.getenv("EDGE_PASSWORD", "edge123")

# 공격 페이로드 (SQL Injection 패턴)
ATTACK_PAYLOADS = [
    "'; DROP TABLE users;--",
    "' OR '1'='1",
    "'; DELETE FROM documents WHERE 1=1;--",
    "' UNION SELECT * FROM users--",
    "admin'--",
    "1' OR '1'='1' /*",
    "'; EXEC sp_MSForEachTable 'DROP TABLE ?';--",
]

def login_to_cloud_server():
    """클라우드 서버에 로그인하여 JWT 토큰 획득"""
    try:
        response = requests.post(
            f"{CLOUD_SERVER_URL}/auth/login",
            json={
                "email": EDGE_EMAIL,
                "password": EDGE_PASSWORD
            },
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            token = data.get('accessToken')
            if token:
                print(f"[로그인 성공] {EDGE_EMAIL}")
                return token
            else:
                print(f"[로그인 실패] 토큰을 받지 못했습니다")
                return None
        else:
            print(f"[로그인 실패] {response.status_code}: {response.text}")
            return None

    except Exception as e:
        print(f"[로그인 오류] {e}")
        return None

def generate_normal_data():
    """정상 센서 데이터 생성"""
    return {
        "robot_id": ROBOT_ID,
        "temperature": round(random.uniform(20.0, 30.0), 2),
        "pressure": round(random.uniform(95.0, 105.0), 2),
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "location": "Factory Floor A",
            "status": "operational"
        }
    }

def generate_attack_data():
    """SQL Injection 공격 데이터 생성"""
    attack_payload = random.choice(ATTACK_PAYLOADS)

    # 다른 필드에 무작위로 주입
    field_choice = random.randint(1, 3)

    if field_choice == 1:
        # robot_id에 주입
        return {
            "robot_id": f"{ROBOT_ID}{attack_payload}",
            "temperature": round(random.uniform(20.0, 30.0), 2),
            "pressure": round(random.uniform(95.0, 105.0), 2),
            "timestamp": datetime.now().isoformat()
        }
    elif field_choice == 2:
        # data 필드에 주입
        return {
            "robot_id": ROBOT_ID,
            "data": attack_payload,
            "timestamp": datetime.now().isoformat()
        }
    else:
        # metadata에 주입
        return {
            "robot_id": ROBOT_ID,
            "temperature": round(random.uniform(20.0, 30.0), 2),
            "pressure": round(random.uniform(95.0, 105.0), 2),
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "location": attack_payload,
                "status": "operational"
            }
        }

def send_data(data, token, attack_mode=False):
    """Edge 서버로 데이터 전송"""
    try:
        print(f"\n{'='*60}")
        print(f"{'[공격 모드]' if attack_mode else '[정상 모드]'} 데이터 전송 중 - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        print(f"로봇 ID: {data.get('robot_id')}")

        if attack_mode:
            # 공격 페이로드 강조 표시
            print(f"[경고] 공격 페이로드 감지됨:")
            print(json.dumps(data, indent=2, ensure_ascii=False))

        # 헤더에 JWT 토큰 포함
        headers = {
            "Content-Type": "application/json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # POST 요청 전송
        response = requests.post(
            EDGE_SERVER_URL,
            json=data,
            headers=headers,
            timeout=5
        )

        # 응답 확인
        if response.status_code == 200:
            print(f"[성공] 응답: {response.status_code}")
            print(f"  {response.json()}")
        else:
            print(f"[오류] {response.status_code}")
            print(f"  {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"[연결 오류] {EDGE_SERVER_URL}에 연결할 수 없습니다")
        print(f"  Edge 서버가 실행 중인지 확인하세요!")
    except requests.exceptions.Timeout:
        print(f"[타임아웃] 서버가 5초 내에 응답하지 않았습니다")
    except Exception as e:
        print(f"[오류] {e}")

def main():
    """메인 함수"""
    global ROBOT_ID, EDGE_SERVER_URL

    parser = argparse.ArgumentParser(description="SeRVe Edge Server용 로봇 시뮬레이터")
    parser.add_argument("--attack", action="store_true", help="공격 모드 활성화 (SQL Injection)")
    parser.add_argument("--interval", type=int, default=1, help="전송 간격 (초 단위)")
    parser.add_argument("--count", type=int, default=None, help="전송할 메시지 수 (기본값: 무한)")
    parser.add_argument("--robot-id", type=str, default=ROBOT_ID, help="로봇 ID")
    parser.add_argument("--url", type=str, default=EDGE_SERVER_URL, help="Edge 서버 URL")

    args = parser.parse_args()

    # 전역 변수 업데이트
    ROBOT_ID = args.robot_id
    EDGE_SERVER_URL = args.url

    print("=" * 60)
    print("SeRVe 로봇 시뮬레이터")
    print("=" * 60)
    print(f"로봇 ID: {ROBOT_ID}")
    print(f"Edge 서버: {EDGE_SERVER_URL}")
    print(f"클라우드 서버: {CLOUD_SERVER_URL}")
    print(f"모드: {'공격 모드 (SQL Injection)' if args.attack else '정상 모드'}")
    print(f"전송 간격: {args.interval}초")
    print(f"전송 횟수: {'무한 (Ctrl+C로 중지)' if args.count is None else args.count}")
    print("=" * 60)

    # 클라우드 서버에 로그인하여 토큰 획득
    token = login_to_cloud_server()
    if not token:
        print("\n[오류] 로그인에 실패했습니다. 종료합니다.")
        print("  .env 파일의 EDGE_EMAIL, EDGE_PASSWORD를 확인하세요.")
        return

    # 전송 루프
    count = 0
    try:
        while True:
            # 데이터 생성
            if args.attack:
                data = generate_attack_data()
            else:
                data = generate_normal_data()

            # 데이터 전송
            send_data(data, token, attack_mode=args.attack)

            # 카운터 증가
            count += 1

            # 횟수 제한 확인
            if args.count is not None and count >= args.count:
                print(f"\n[완료] {count}개 메시지 전송 완료. 종료합니다.")
                break

            # 대기
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n\n[중단] 사용자에 의해 중단됨. {count}개 메시지 전송 완료. 종료합니다.")

if __name__ == "__main__":
    main()
