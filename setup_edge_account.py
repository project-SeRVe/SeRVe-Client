#!/usr/bin/env python3
"""
Automated Edge Account Setup
Creates edge account, repository, and updates .env file with TEAM_ID
"""

import sys
from pathlib import Path

# Add SeRVe-Client to path
sys.path.insert(0, str(Path(__file__).parent.parent / "SeRVe-Client"))

from serve_sdk import ServeClient

# Configuration
CLOUD_URL = "http://localhost:8080"
EDGE_EMAIL = "edge@serve.local"
EDGE_PASSWORD = "edge123"
REPO_NAME = "Edge Server Repository"
REPO_DESC = "Repository for edge server data collection and processing"

def update_env_file(team_id):
    """Update .env file with TEAM_ID"""
    env_file = Path(__file__).parent / ".env"

    # Read current .env content
    if env_file.exists():
        with open(env_file, 'r') as f:
            lines = f.readlines()

        # Update TEAM_ID line
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('TEAM_ID='):
                lines[i] = f'TEAM_ID={team_id}\n'
                updated = True
                break

        # If TEAM_ID line doesn't exist, add it
        if not updated:
            lines.append(f'\nTEAM_ID={team_id}\n')

        # Write back
        with open(env_file, 'w') as f:
            f.writelines(lines)
    else:
        # Create new .env file
        with open(env_file, 'w') as f:
            f.write(f"""# SeRVe Edge Server Configuration

# Cloud Server
CLOUD_URL={CLOUD_URL}
EDGE_EMAIL={EDGE_EMAIL}
EDGE_PASSWORD={EDGE_PASSWORD}

# Team ID (Repository ID from cloud server)
TEAM_ID={team_id}
""")

    print(f"✓ Updated .env file with TEAM_ID={team_id}")

def main():
    """Main setup function"""
    print("=" * 60)
    print("SeRVe Edge Account Setup")
    print("=" * 60)

    # Initialize client
    print(f"\n1. Connecting to cloud server: {CLOUD_URL}")
    client = ServeClient(server_url=CLOUD_URL)
    print(f"   ✓ Connected")

    # Signup
    print(f"\n2. Creating edge account: {EDGE_EMAIL}")
    success, msg = client.signup(EDGE_EMAIL, EDGE_PASSWORD)

    if success:
        print(f"   ✓ Account created: {msg}")
    elif "already exists" in msg.lower() or "duplicate" in msg.lower():
        print(f"   ℹ Account already exists, skipping signup")
    else:
        print(f"   ✗ Signup failed: {msg}")
        return False

    # Login
    print(f"\n3. Logging in as {EDGE_EMAIL}")
    success, msg = client.login(EDGE_EMAIL, EDGE_PASSWORD)

    if not success:
        print(f"   ✗ Login failed: {msg}")
        return False

    print(f"   ✓ Logged in: {msg}")

    # Get existing repositories
    print(f"\n4. Checking for existing repositories")
    repos, msg = client.get_my_repositories()

    if repos and len(repos) > 0:
        print(f"   ℹ Found {len(repos)} existing repository(ies)")

        # Use first repository
        repo = repos[0]
        repo_id = repo.get('Teamid') or repo.get('teamid')
        repo_name = repo.get('name')

        print(f"   ✓ Using existing repository: {repo_name} (ID: {repo_id})")
    else:
        # Create new repository
        print(f"\n5. Creating repository: {REPO_NAME}")
        repo_id, msg = client.create_repository(REPO_NAME, REPO_DESC)

        if not repo_id:
            print(f"   ✗ Repository creation failed: {msg}")
            return False

        print(f"   ✓ Repository created: {msg}")
        print(f"   ✓ Repository ID: {repo_id}")

    # Update .env file
    print(f"\n6. Updating .env file")
    update_env_file(repo_id)

    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print(f"\nEdge Account: {EDGE_EMAIL}")
    print(f"Repository ID: {repo_id}")
    print(f"\nYou can now run the edge server with:")
    print(f"  cd edge-server")
    print(f"  docker-compose up --build")
    print("=" * 60)

    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
