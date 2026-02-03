"""
Silicon Casino - Main entry point for Railway Railpack deployment.
This file imports and runs the FastAPI application from the backend package.
"""
import os
import subprocess
import sys

# Run migrations before starting the server
print("Running database migrations...")
try:
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    print("Migrations complete.")
except subprocess.CalledProcessError as e:
    print(f"Migration failed: {e}")
    # Continue anyway - migrations might already be applied

# Import and run the app
import uvicorn
from backend.main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
