# Debug Log - Database Connection Conflict

This log explains why the `test_pipeline.py` script is currently failing at **Test 01 (DB Connection)**.

## 1. Symptom
When running `python test_pipeline.py`, the following error occurs:
```text
DB Error: connection to server at "127.0.0.1", port 5432 failed: fe_sendauth: no password supplied
```

## 2. Diagnosis
I performed a system-level check for processes listening on port **5432** (the default PostgreSQL port) and found a conflict:

### Port Usage Analysis (from `netstat -ano`):
| Process ID (PID) | Image Name | Role |
| :--- | :--- | :--- |
| **8472** | `postgres.exe` | **Local Windows Service** (requires password) |
| **18328** | `com.docker.backend.exe` | **Docker Desktop** (forwards to container) |

### Confirmed Authentication Setting:
The Docker container `news_system_postgres` is configured with:
```text
POSTGRES_HOST_AUTH_METHOD=trust
```
This means the container **should not** require a password. However, because the Windows service (`postgres.exe`) is also listening on the same port, it intercepts the connection request. Since it expects a password (which is not provided in Test 01), it returns the `fe_sendauth` error.

## 3. Verification of Docker Connection
I verified that the database **inside** the Docker container is working correctly by running a command directly within it:
```powershell
docker exec news_system_postgres psql -U postgres -d news_system -c "SELECT 1"
```
**Result**: `PASS` (The database responded with `1`).

## 4. Final Conclusion
The issue is **not** in the `test_pipeline.py` script or the database container. The error is a **Port Conflict** on your host machine.

### Required Actions:
1.  **Stop the Windows Service**: Open an Administrative PowerShell and run:
    ```powershell
    net stop postgresql-x64-16
    ```
2.  **Restart Docker Container**: If the container died during the conflict, restart it:
    ```powershell
    docker start news_system_postgres
    ```
3.  **Run Test**:
    ```powershell
    python test_pipeline.py
    ```
