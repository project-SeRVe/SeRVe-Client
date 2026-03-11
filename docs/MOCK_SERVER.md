# Mock SeRVe Server

A lightweight Flask-based mock server that simulates the SeRVe microservice architecture for local testing.

## Overview

This mock server implements all major endpoints of the SeRVe backend:
- **Auth Service**: User registration, login, and authentication
- **Team Service**: Repository and member management
- **Core Service**: Task and demo data management

## Features

- ✅ **In-memory storage** - No database required
- ✅ **All SeRVe APIs** - Auth, Team, Core services on single port (8080)
- ✅ **MSA-compatible** - Can simulate separate service URLs
- ✅ **CORS enabled** - Works with web frontends
- ✅ **Mock authentication** - Simple token-based auth for testing
- ✅ **Zero configuration** - Just run and test

## Installation

```bash
# Install dependencies
pip install flask flask-cors

# Make executable
chmod +x mock_server.py
```

## Usage

### Start Server

```bash
# Run in foreground
python mock_server.py

# Run in background
python mock_server.py > mock_server.log 2>&1 &
```

Server starts on `http://localhost:8080` by default.

### Health Check

```bash
curl http://localhost:8080/health
```

### Test with SeRVe CLI

```bash
# Configure CLI to use mock server
# In your CLI context or config, set server URL to http://localhost:8080

# Test signup
serve auth signup

# Test login
serve auth login

# Test repository operations
serve repo create "Test Repo"
serve repo list
```

## API Endpoints

### Auth Service (`/auth/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | User registration |
| POST | `/auth/login` | User login |
| DELETE | `/auth/me` | Account deletion |
| GET | `/auth/public-key?email=` | Get user's public key |

### Team Service (`/api/repositories/*`, `/api/teams/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/repositories` | Create repository |
| GET | `/api/repositories?userId=` | List repositories |
| DELETE | `/api/repositories/{id}` | Delete repository |
| GET | `/api/repositories/{id}/keys` | Get encrypted team key |
| POST | `/api/teams/{id}/members` | Invite member |
| GET | `/api/teams/{id}/members` | List members |
| DELETE | `/api/teams/{id}/members/{userId}` | Kick member |
| PUT | `/api/teams/{id}/members/{userId}` | Update member role |
| POST | `/api/teams/{id}/members/rotate-keys` | Rotate team keys |

### Core Service (`/api/teams/*/tasks`, `/api/teams/*/demos`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/teams/{id}/tasks` | Upload task |
| GET | `/api/teams/{id}/tasks` | List tasks |
| GET | `/api/tasks/{id}/data` | Download task |
| DELETE | `/api/teams/{id}/tasks/{taskId}` | Delete task |
| POST | `/api/teams/{id}/demos` | Upload demos |
| GET | `/api/sync/demos?teamId=&lastVersion=` | Sync demos |
| DELETE | `/api/teams/{id}/demos/{index}` | Delete demo |

## Testing

Run the included test script:

```bash
./test_mock_server.sh
```

Expected output:
- ✅ User signup succeeds
- ✅ Login returns token and user ID
- ✅ Repository creation works
- ✅ Task upload/download works
- ✅ Member management works

## Architecture

```
mock_server.py (Port 8080)
├── Auth Service (/auth/*)
├── Team Service (/api/repositories/*, /api/teams/*)
└── Core Service (/api/teams/*/tasks, /api/sync/demos)
```

Unlike the real SeRVe backend (which runs on ports 8081, 8082, 8083 behind Nginx), this mock server consolidates all services on port 8080 for simplicity.

## Limitations

- **In-memory only** - Data lost on restart
- **No encryption** - Stores encrypted blobs as-is without validation
- **Simple auth** - Mock tokens without JWT validation
- **No persistence** - Use for testing only, not production

## Differences from Real Server

| Feature | Real Server | Mock Server |
|---------|------------|-------------|
| Ports | 8081 (Auth), 8082 (Team), 8083 (Core) | 8080 (All) |
| Database | PostgreSQL | In-memory dict |
| Auth | JWT with signing | Mock tokens |
| Encryption | Tink/Hybrid | Stores as-is |
| Password | Bcrypt hashed | Plain text |

## Development

To add new endpoints:

1. Add route handler in appropriate section (Auth/Team/Core)
2. Follow existing patterns for auth and response format
3. Update this README with new endpoint
4. Add test case to `test_mock_server.sh`

## Stopping Server

```bash
# Find PID
ps aux | grep mock_server.py

# Kill process
kill <PID>

# Or if started with test script
pkill -f mock_server.py
```

## License

Part of SeRVe-Client project.
