from fastapi import FastAPI;
from app.core.security import verify_password
from app.core.database import init_database
from app.routes.user_routes import router as user_router
from app.routes.vault_routes import router as vault_router

app = FastAPI(title='smartvault_api')

# Create all tables if they don't exist
init_database()

# Include routes
app.include_router(user_router)
app.include_router(vault_router)