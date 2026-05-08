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
    
    # 2. Trigger Playwright validation
    result = await sunat_service.test_connection(
        ruc=company.ruc,
        user=cred.sol_user,
        password_encrypted=cred.sol_password_encrypted
    )
    
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["message"])
    
    return result

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
