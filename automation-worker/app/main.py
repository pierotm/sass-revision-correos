import asyncio
import logging
import sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("automation-worker")

# Setup database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@osorio-db:5432/osorio_platform")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import shared logic
# Note: PYTHONPATH should be configured to include /app/backend-api and /app/shared
from shared.models import Company, Credential, Execution, Notification, Document, ExecutionStatus, WorkerStatus
from app.services.sunat import sunat_service # Reusing the validated service

async def run_worker_cycle():
    logger.info("Starting Worker Cycle v1 (One-Shot)")
    db = SessionLocal()
    
    try:
        # 1. Update Worker Status
        worker_status = db.query(WorkerStatus).filter(WorkerStatus.worker_name == "worker-01").first()
        if not worker_status:
            worker_status = WorkerStatus(worker_name="worker-01")
            db.add(worker_status)
        
        worker_status.last_seen = datetime.utcnow()
        worker_status.current_job = "Selecting company..."
        db.commit()

        # 2. Select a company to process (Active & oldest last_checked_at)
        company = db.query(Company).filter(Company.is_active == True).order_by(Company.last_checked_at.asc().nulls_first()).first()
        
        if not company:
            logger.info("No active companies found to process.")
            return

        if not company.credentials:
            logger.warning(f"Company {company.name} (RUC {company.ruc}) has no credentials. Skipping.")
            company.last_checked_at = datetime.utcnow() # Mark so it doesn't get stuck
            db.commit()
            return

        logger.info(f"Processing company: {company.name} (RUC {company.ruc})")
        worker_status.current_job = f"Scraping {company.ruc}"
        db.commit()

        # 3. Create Execution record
        execution = Execution(
            company_id=company.id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        # 4. Run the scraper
        result = await sunat_service.test_connection(
            ruc=company.ruc,
            user=company.credentials.sol_user,
            password_encrypted=company.credentials.sol_password_encrypted
        )

        if result["success"]:
            logger.info(f"Scrape successful for {company.ruc}")
            execution.status = ExecutionStatus.SUCCESS
            
            # Create Notification and Document records
            notif_data = result.get("data", {})
            import uuid
            notification = Notification(
                execution_id=execution.id,
                external_reference=str(uuid.uuid4())[:20],
                title=notif_data.get("asunto", "Carga Automática"),
                received_at=datetime.utcnow()
            )
            db.add(notification)
            db.flush()

            document = Document(
                notification_id=notification.id,
                filename=notif_data.get("filename"),
                file_path=notif_data.get("file_path"),
                file_hash=notif_data.get("file_hash")
            )
            db.add(document)
            
            company.last_checked_at = datetime.utcnow()
            worker_status.jobs_processed += 1
        else:
            logger.error(f"Scrape failed for {company.ruc}: {result['message']}")
            execution.status = ExecutionStatus.FAILED
            execution.error_message = result["message"]
            company.last_checked_at = datetime.utcnow() # Still mark to move to next in queue

        execution.finished_at = datetime.utcnow()
        worker_status.current_job = "Idle"
        db.commit()
        logger.info(f"Worker cycle finished for {company.ruc}")

    except Exception as e:
        logger.error(f"Worker error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_worker_cycle())
