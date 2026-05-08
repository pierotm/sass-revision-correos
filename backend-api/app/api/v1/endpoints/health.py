from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.dependencies import get_db

router = APIRouter()

@router.get("/")
def health_check():
    return {"status": "ok", "service": "backend-api"}

@router.get("/db")
def health_check_db(db: Session = Depends(get_db)):
    try:
        # Try a simple query to verify DB connection
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "details": str(e)}
