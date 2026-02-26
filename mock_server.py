import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import uuid

# In-memory database
db = {
    "users": {}, # email -> {"password": "", "publicKey": "", "encryptedPrivateKey": "", "userId": ""}
    "teams": {}, # teamId -> {"name": "", "ownerId": "", "encryptedTeamKey": ""}
    "members": {}, # teamId -> list of user emails
    "documents": {}, # teamId -> list of dicts {"documentId", "fileName", "fileType", "encryptedBlob", "uploaderId", "uploadedAt", "size"}
    "chunks": {} # docId -> list of dicts
}

class MockBackendHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE, PUT')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def send_json(self, status, data):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def parse_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8'))

    def do_POST(self):
        try:
            body = self.parse_body()
            
            if self.path == '/auth/signup':
                email = body.get('email')
                
                # 중복 가입 에러 제거: 로컬 테스트 편의를 위해 동일한 이메일로 가입 시 덮어쓰기 허용
                existing_user_id = db["users"].get(email, {}).get("userId", str(uuid.uuid4()))
                
                db["users"][email] = {
                    "userId": existing_user_id,
                    "password": body.get('password'),
                    "publicKey": body.get('publicKey'),
                    "encryptedPrivateKey": body.get('encryptedPrivateKey')
                }
                return self.send_json(201, {"message": "Signup successful"})

            elif self.path == '/auth/login':
                email = body.get('email')
                password = body.get('password')
                user = db["users"].get(email)
                
                if user and user["password"] == password:
                    return self.send_json(200, {
                        "accessToken": f"mock-token-for-{user['userId']}",
                        "userId": user["userId"],
                        "email": email,
                        "encryptedPrivateKey": user["encryptedPrivateKey"]
                    })
                return self.send_json(401, {"message": "Invalid email or password"})
                
            elif self.path == '/auth/reset-password':
                email = body.get('email')
                new_password = body.get('newPassword')
                new_encrypted_private_key = body.get('encryptedPrivateKey')
                
                if email in db["users"]:
                    db["users"][email]["password"] = new_password
                    if new_encrypted_private_key:
                        db["users"][email]["encryptedPrivateKey"] = new_encrypted_private_key
                    return self.send_json(200, {"message": "Password reset successful"})
                return self.send_json(404, {"message": "User not found"})
            elif self.path == '/api/repositories':
                team_id = str(uuid.uuid4())
                db["teams"][team_id] = {
                    "name": body.get('name'),
                    "description": body.get('description'),
                    "ownerId": body.get('ownerId'),
                    "encryptedTeamKey": body.get('encryptedTeamKey')
                }
                return self.send_json(201, team_id)  # API client expects just string or dict
                
            elif self.path.startswith('/api/teams/') and '/members' in self.path:
                team_id = self.path.split('/')[3]
                email = body.get('email')
                encrypted_team_key = body.get('encryptedTeamKey')
                
                if team_id not in db["members"]:
                    db["members"][team_id] = []
                
                user = db["users"].get(email)
                if not user:
                    return self.send_json(404, {"message": "User not found"})
                    
                db["members"][team_id].append({
                    "userId": user["userId"],
                    "email": email,
                    "encryptedTeamKey": encrypted_team_key,
                    "role": "MEMBER"
                })
                return self.send_json(200, {"message": "Member invited"})
                
            elif self.path.startswith('/api/teams/') and self.path.endswith('/chunks'):
                team_id = self.path.split('/')[3]
                if team_id not in db["documents"]:
                    db["documents"][team_id] = []
                    
                doc_id = str(uuid.uuid4())
                file_name = body.get("fileName", "Unknown")
                encrypted_dek = body.get("encryptedDEK", "")
                
                db["documents"][team_id].append({
                    "docId": doc_id,
                    "documentId": doc_id,
                    "fileName": file_name,
                    "fileType": "demo-data",
                    "encryptedDEK": encrypted_dek,
                    "uploaderId": "mock-uploader",
                    "uploadedAt": "2026-02-20",
                    "size": 1024
                })
                
                # Mock chunk generation
                db["chunks"][doc_id] = []
                for chunk in body.get("chunks", []):
                    db["chunks"][doc_id].append({
                        "documentId": doc_id,
                        "chunkId": str(uuid.uuid4()),
                        "chunkIndex": chunk.get("chunkIndex", 0),
                        "encryptedBlob": chunk.get("encryptedBlob", ""),
                        "version": 1,
                        "isDeleted": False
                    })
                
                return self.send_json(200, {"message": "Chunks uploaded", "documentId": doc_id})
                
            # Default mock for other POST endpoints
            return self.send_json(200, {"message": f"Mock POST success for {self.path}"})
            
        except Exception as e:
            self.send_json(500, {"message": str(e)})

    def do_GET(self):
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            query = urllib.parse.parse_qs(parsed_path.query)

            if path == '/api/repositories':
                user_id = query.get('userId', [''])[0]
                repos = []
                for tid, t in db["teams"].items():
                    if t["ownerId"] == user_id:
                        repos.append({"id": tid, "name": t["name"], "description": t["description"], "role": "OWNER"})
                    else:
                        for m in db["members"].get(tid, []):
                            if m["userId"] == user_id:
                                repos.append({"id": tid, "name": t["name"], "description": t["description"], "role": m["role"]})
                                break
                return self.send_json(200, repos)
                
            elif path.startswith('/api/repositories/') and path.endswith('/keys'):
                # Extract repo ID
                repo_id = path.split('/')[3]
                team = db["teams"].get(repo_id)
                if team:
                    user_id = query.get('userId', [''])[0]
                    if team["ownerId"] == user_id:
                        return self.send_json(200, team["encryptedTeamKey"])
                    
                    for m in db["members"].get(repo_id, []):
                        if m["userId"] == user_id:
                            return self.send_json(200, m["encryptedTeamKey"])
                            
                    return self.send_json(403, {"message": "Not a participant"})
                return self.send_json(404, {"message": "Team not found"})

            elif path == '/auth/public-key':
                email = query.get('email', [''])[0]
                user = db["users"].get(email)
                if user:
                    # Client expects JSON string representing public key, which was stored as string/dict
                    pub_key = user["publicKey"]
                    # Usually publickey is sent as dict but crypto_utils expects json string
                    if isinstance(pub_key, str):
                        pub_key = json.loads(pub_key)
                    return self.send_json(200, pub_key)
                return self.send_json(404, {"message": "User not found"})

            elif path.startswith('/api/teams/') and path.endswith('/documents'):
                team_id = path.split('/')[3]
                docs = db["documents"].get(team_id, [])
                return self.send_json(200, docs)

            elif path.startswith('/api/documents/') and path.endswith('/chunks/sync'):
                doc_id = path.split('/')[3]
                chunks = db["chunks"].get(doc_id, [])
                return self.send_json(200, chunks)

            elif path == '/api/sync/chunks':
                team_id = query.get('teamId', [''])[0]
                docs = db["documents"].get(team_id, [])
                all_chunks = []
                for doc in docs:
                    all_chunks.extend(db["chunks"].get(doc["documentId"], []))
                return self.send_json(200, all_chunks)

            # Default mock for other GET endpoints
            return self.send_json(200, [])

        except Exception as e:
            self.send_json(500, {"message": str(e)})

    def do_DELETE(self):
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            query = urllib.parse.parse_qs(parsed_path.query)

            if path == '/auth/me':
                # 1. 토큰 추출 (Bearer Token)
                auth_header = self.headers.get('Authorization')
                if not auth_header or not auth_header.startswith('Bearer '):
                    return self.send_json(401, {"message": "Unauthorized"})
                
                token = auth_header.split(' ')[1]
                
                # 2. 토큰으로 사용자 찾기 (목 서버이므로 토큰 == userId 문자열을 단순 매핑)
                # db["users"] 는 email이 키이므로 순회
                target_email = None
                for email, u in db["users"].items():
                    if u["userId"] == token or u["userId"] in token:
                        target_email = email
                        break
                        
                if target_email:
                    del db["users"][target_email]
                    return self.send_json(200, {"message": "Account deleted"})
                else:
                    return self.send_json(404, {"message": "User not found"})

            elif path.startswith('/api/teams/') and '/members/' in path:
                parts = path.split('/')
                team_id = parts[3]
                target_user_id = parts[5]
                admin_id = query.get('adminId', [''])[0]

                team = db["teams"].get(team_id)
                if not team:
                    return self.send_json(404, {"message": "Team not found"})

                if team["ownerId"] != admin_id:
                    return self.send_json(403, {"message": "Not an admin"})

                members = db["members"].get(team_id, [])
                new_members = [m for m in members if m["userId"] != target_user_id and m["email"] != target_user_id]
                db["members"][team_id] = new_members

                return self.send_json(200, {"success": True, "message": "Member kicked", "keyRotationRequired": False})

            return self.send_json(200, {"message": f"Mock DELETE success for {path}"})

        except Exception as e:
            self.send_json(500, {"message": str(e)})

if __name__ == '__main__':
    port = 8080
    server = HTTPServer(('localhost', port), MockBackendHandler)
    print(f"Mock server running on http://localhost:{port}...")
    print("Keep this terminal open to test your CLI commands.")
    server.serve_forever()
