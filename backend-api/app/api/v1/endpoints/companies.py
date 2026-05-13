from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.dependencies import get_db
from app.schemas.company import Company, CompanyCreate
from shared.models import Company as CompanyModel, Credential as CredentialModel
from app.services.sunat import sunat_service

router = APIRouter()

@router.post("/{company_id}/test-connection")
async def test_company_connection(company_id: int, db: Session = Depends(get_db)):
    # 1. Get company and credentials
    company = db.query(CompanyModel).filter(CompanyModel.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    cred = db.query(CredentialModel).filter(CredentialModel.company_id == company_id).first()
    if not cred:
        raise HTTPException(status_code=400, detail="Company has no credentials configured")
    
    # 2. Trigger Playwright validation (Login + Scrape + Download)
    result = await sunat_service.test_connection(
        ruc=company.ruc,
        user=cred.sol_user,
        password_encrypted=cred.sol_password_encrypted
    )
    
    if result["success"]:
        # Persist results in DB
        from shared.models import Execution, Notification, Document, ExecutionStatus
        import uuid
        from datetime import datetime

        # 1. Create Execution
        execution = Execution(
            company_id=company_id,
            status=ExecutionStatus.SUCCESS,
            finished_at=datetime.utcnow()
        )
        db.add(execution)
        db.flush() 

        # 2. Create Notification
        notif_data = result.get("data", {})
        notification = Notification(
            execution_id=execution.id,
            external_reference=str(uuid.uuid4())[:20], 
            title=notif_data.get("asunto", "Validación Descarga"),
            received_at=datetime.utcnow()
        )
        db.add(notification)
        db.flush()

        # 3. Create Document
        document = Document(
            notification_id=notification.id,
            filename=notif_data.get("filename"),
            file_path=notif_data.get("file_path"),
            file_hash=notif_data.get("file_hash")
        )
        db.add(document)
        db.commit()

        return result
    
    raise HTTPException(status_code=401, detail=result["message"])

@router.post("/", response_model=Company, status_code=status.HTTP_201_CREATED)
def create_company(company_in: CompanyCreate, db: Session = Depends(get_db)):
    # Check if RUC already exists
    db_company = db.query(CompanyModel).filter(CompanyModel.ruc == company_in.ruc).first()
    if db_company:
        raise HTTPException(
            status_code=400,
            detail=f"Company with RUC {company_in.ruc} already exists."
        )
    
    new_company = CompanyModel(
        name=company_in.name,
        ruc=company_in.ruc
    )
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    return new_company

@router.get("/", response_model=List[Company])
def list_companies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    companies = db.query(CompanyModel).offset(skip).limit(limit).all()
    return companies
