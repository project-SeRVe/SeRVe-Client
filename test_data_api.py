from src.cli.context import CLIContext
import uuid

def test_data_flow():
    ctx = CLIContext()
    
    print("\n--- 1. Signup & Login ---")
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    password = "password123"
    
    success, msg = ctx.client.signup(email, password)
    print(f"Signup: {success}, {msg}")
    
    success, msg = ctx.client.login(email, password)
    print(f"Login: {success}, {msg}")
    
    print("\n--- 2. Create Repository ---")
    repo_name = f"TestRepo_{uuid.uuid4().hex[:6]}"
    repo_id, msg = ctx.client.create_repository(repo_name, "For data testing")
    print(f"Create Repo: {repo_id is not None}, {msg}")
    
    if not repo_id:
        print("Failed to create repo, exiting.")
        return

    print("\n--- 3. Upload Data ---")
    task_name = "test_task"
    data_id = "test_data_001"
    
    metadata = f"Task: {task_name}\nDataID: {data_id}\nDesc: test metadata\nRobotID: robot123"
    chunk_data = [{"chunkIndex": 0, "data": metadata}]
    
    success, msg = ctx.client.upload_chunks_to_document(
        file_name=f"{task_name}_{data_id}",
        repo_id=repo_id,
        chunks_data=chunk_data
    )
    print(f"Upload Data: {success}, {msg}")
    
    print("\n--- 4. List Data ---")
    docs, msg = ctx.client.get_documents(repo_id)
    print(f"List Data Success: {docs is not None}, Msg: {msg}")
    if docs:
        for doc in docs:
            print(f"  - Found doc: {doc.get('fileName')}")

    print("\n--- 5. Download Data ---")
    chunks, msg = ctx.client.download_chunks_from_document(f"{task_name}_{data_id}", repo_id)
    print(f"Download Data Success: {chunks is not None}, Msg: {msg}")
    if chunks:
         preview = chunks[0].get("data", "")[:50].replace('\n', ' ')
         print(f"  - Preview: {preview}...")

    print("\n--- 6. Pull Data (Sync) ---")
    success, msg_or_chunks = ctx.client.sync_team_chunks(repo_id, -1)
    print(f"Pull Data Success: {success}")
    if success:
        print(f"  - Pulled {len(msg_or_chunks)} chunks for the team.")

if __name__ == "__main__":
    test_data_flow()
