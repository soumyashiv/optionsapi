import uvicorn
from fastapi.staticfiles import StaticFiles
from api.index import app

# Mount public directory for local testing
app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    print("Starting Option Chain Viewer Server...")
    print("Go to http://localhost:8000 to view the app.")
    uvicorn.run("run:app", host="0.0.0.0", port=8000, reload=True)
