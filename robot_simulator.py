#!/usr/bin/env python3
"""
Robot Simulator
Sends sensor data to edge server (normal or attack mode)
"""

import time
import argparse
import random
import json
import requests
from datetime import datetime

# Robot configuration
ROBOT_ID = "AGV-001"
EDGE_SERVER_URL = "http://localhost:9000/api/sensor-data"

# Attack payloads (SQL Injection patterns)
ATTACK_PAYLOADS = [
    "'; DROP TABLE users;--",
    "' OR '1'='1",
    "'; DELETE FROM documents WHERE 1=1;--",
    "' UNION SELECT * FROM users--",
    "admin'--",
    "1' OR '1'='1' /*",
    "'; EXEC sp_MSForEachTable 'DROP TABLE ?';--",
]

def generate_normal_data():
    """Generate normal sensor data"""
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
    """Generate attack data with SQL injection"""
    attack_payload = random.choice(ATTACK_PAYLOADS)

    # Randomly inject into different fields
    field_choice = random.randint(1, 3)

    if field_choice == 1:
        # Inject into robot_id
        return {
            "robot_id": f"{ROBOT_ID}{attack_payload}",
            "temperature": round(random.uniform(20.0, 30.0), 2),
            "pressure": round(random.uniform(95.0, 105.0), 2),
            "timestamp": datetime.now().isoformat()
        }
    elif field_choice == 2:
        # Inject into data field
        return {
            "robot_id": ROBOT_ID,
            "data": attack_payload,
            "timestamp": datetime.now().isoformat()
        }
    else:
        # Inject into metadata
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

def send_data(data, attack_mode=False):
    """Send data to edge server"""
    try:
        print(f"\n{'='*60}")
        print(f"{'[ATTACK MODE]' if attack_mode else '[NORMAL MODE]'} Sending data at {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        print(f"Robot ID: {data.get('robot_id')}")

        if attack_mode:
            # Highlight attack payload
            print(f"⚠️  ATTACK PAYLOAD DETECTED:")
            print(json.dumps(data, indent=2))

        # Send POST request
        response = requests.post(
            EDGE_SERVER_URL,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=5
        )

        # Check response
        if response.status_code == 200:
            print(f"✓ Response: {response.status_code}")
            print(f"  {response.json()}")
        else:
            print(f"✗ Error: {response.status_code}")
            print(f"  {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"✗ Connection Error: Cannot connect to {EDGE_SERVER_URL}")
        print(f"  Make sure the edge server is running!")
    except requests.exceptions.Timeout:
        print(f"✗ Timeout: Server did not respond within 5 seconds")
    except Exception as e:
        print(f"✗ Error: {e}")

def main():
    """Main function"""
    global ROBOT_ID, EDGE_SERVER_URL

    parser = argparse.ArgumentParser(description="Robot Simulator for SeRVe Edge Server")
    parser.add_argument("--attack", action="store_true", help="Enable attack mode (SQL injection)")
    parser.add_argument("--interval", type=int, default=1, help="Interval between sends (seconds)")
    parser.add_argument("--count", type=int, default=None, help="Number of messages to send (default: infinite)")
    parser.add_argument("--robot-id", type=str, default=ROBOT_ID, help="Robot ID")
    parser.add_argument("--url", type=str, default=EDGE_SERVER_URL, help="Edge server URL")

    args = parser.parse_args()

    # Update globals
    ROBOT_ID = args.robot_id
    EDGE_SERVER_URL = args.url

    print("=" * 60)
    print("SeRVe Robot Simulator")
    print("=" * 60)
    print(f"Robot ID: {ROBOT_ID}")
    print(f"Edge Server: {EDGE_SERVER_URL}")
    print(f"Mode: {'ATTACK (SQL Injection)' if args.attack else 'NORMAL'}")
    print(f"Interval: {args.interval} second(s)")
    print(f"Count: {'Infinite (Ctrl+C to stop)' if args.count is None else args.count}")
    print("=" * 60)

    # Send loop
    count = 0
    try:
        while True:
            # Generate data
            if args.attack:
                data = generate_attack_data()
            else:
                data = generate_normal_data()

            # Send data
            send_data(data, attack_mode=args.attack)

            # Increment counter
            count += 1

            # Check count limit
            if args.count is not None and count >= args.count:
                print(f"\n✓ Sent {count} messages. Exiting.")
                break

            # Wait
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n\n✓ Interrupted by user. Sent {count} messages. Exiting.")

if __name__ == "__main__":
    main()
