from fastapi import FastAPI;
from app.core.security import verify_password
from app.core.database import init_database
from app.routes.user_routes import router as user_router
from app.routes.uservault_routes import router as vault_router
from app.routes.keypadpin_routes import router as keypadpin_router
from app.routes.log_routes import router as log_router
from app.routes.nfccard_routes import router as nfccard_routes
from app.routes.uservault_routes import router as uservault_router


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title='smartvault_api')

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables if they don't exist
try: 
    init_database()
    print("Application startup: Database initialized successfully")
except Exception as e:
    print(f"Application startup failed: Database init error - {e}")
    raise

# Include routes
app.include_router(user_router)
app.include_router(vault_router)
app.include_router(keypadpin_router)
app.include_router(log_router)
app.include_router(nfccard_routes)
app.include_router(uservault_router)


from app.websockets.LogWebSocketHandler import LogWebSocketHandler

from fastapi import WebSocket

