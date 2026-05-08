from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_db
from app.schemas.credential import Credential, CredentialCreate
from shared.models import Credential as CredentialModel, Company as CompanyModel
from shared.security import SecurityManager

router = APIRouter()
security = SecurityManager()

@router.post("/{company_id}/credentials/", response_model=Credential, status_code=status.HTTP_201_CREATED)
def set_company_credentials(
    company_id: int, 
    cred_in: CredentialCreate, 
    db: Session = Depends(get_db)
):
    # 1. Verify company exists
    company = db.query(CompanyModel).filter(CompanyModel.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # 2. Encrypt the password
    encrypted_password = security.encrypt(cred_in.sol_password)
    
    # 3. Check if credentials already exist for this company
    db_cred = db.query(CredentialModel).filter(CredentialModel.company_id == company_id).first()
    
    if db_cred:
        # Update existing
        db_cred.sol_user = cred_in.sol_user
        db_cred.sol_password_encrypted = encrypted_password
    else:
        # Create new
        db_cred = CredentialModel(
            company_id=company_id,
            sol_user=cred_in.sol_user,
            sol_password_encrypted=encrypted_password
        )
        db.add(db_cred)
    
    db.commit()
    db.refresh(db_cred)
    return db_cred
