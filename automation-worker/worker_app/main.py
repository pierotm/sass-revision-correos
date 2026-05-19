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
from shared.services.email_service import email_service

TARGET_EMAIL = os.getenv("NOTIFICATION_EMAIL_TO", "test@example.com")

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time

async def run_worker_cycle():
    start_time = time.time()
    logger.info("--- Starting Automation Cycle ---")
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
            logger.info("No active companies found to process. Sleeping until next tick.")
            return

        logger.info(f"Picked company for this cycle: {company.name} (RUC {company.ruc})")
        # ... (rest of the logic remains similar but wrapped in logs)
        
        if not company.credentials:
            logger.warning(f"Company {company.name} has no credentials. Skipping.")
            company.last_checked_at = datetime.utcnow()
            db.commit()
            return

        worker_status.current_job = f"Processing {company.ruc}"
        db.commit()

        # Create Execution
        execution = Execution(
            company_id=company.id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        # Run the scraper
        result = await sunat_service.test_connection(
            ruc=company.ruc,
            user=company.credentials.sol_user,
            password_encrypted=company.credentials.sol_password_encrypted
        )

        if result["success"]:
            logger.info(f"Cycle SUCCESS for {company.ruc}")
            execution.status = ExecutionStatus.SUCCESS
            
            # Persist documents (reusing previous logic)
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
            db.flush() # Ensure document gets an ID if needed
            
            # Delivery Phase
            if not document.is_notified:
                try:
                    logger.info(f"Attempting to send email notification for {document.filename}...")
                    success = email_service.send_notification_email(
                        to_email=TARGET_EMAIL,
                        company_name=company.name,
                        ruc=company.ruc,
                        file_path=document.file_path,
                        original_subject=notification.title
                    )
                    if success:
                        document.is_notified = True
                        document.notified_at = datetime.utcnow()
                        logger.info("Email sent and document marked as notified.")
                except Exception as e:
                    logger.error(f"Email delivery failed: {str(e)}")
                    # We do not fail the cycle, just log it. The document remains is_notified=False.

            company.last_checked_at = datetime.utcnow()
            worker_status.jobs_processed += 1
        else:
            logger.error(f"Cycle FAILED for {company.ruc}: {result['message']}")
            execution.status = ExecutionStatus.FAILED
            execution.error_message = result["message"]
            execution.screenshot_path = result.get("screenshot_path")
            
            # Create a detailed ErrorLog
            from shared.models import ErrorLog
            error_log = ErrorLog(
                execution_id=execution.id,
                error_type=result.get("error_type", "UNKNOWN"),
                message=result.get("message"),
                stack_trace=result.get("stack_trace")
            )
            db.add(error_log)
            
            company.last_checked_at = datetime.utcnow()

        execution.finished_at = datetime.utcnow()
        duration = time.time() - start_time
        worker_status.current_job = "Idle"
        db.commit()
        logger.info(f"--- Cycle Finished. Duration: {duration:.2f}s ---")

    except Exception as e:
        logger.error(f"Critical Worker error: {str(e)}")
        db.rollback()
    finally:
        db.close()

async def main():
    logger.info("Automation Worker v2 started with APScheduler")
    scheduler = AsyncIOScheduler()
    # Schedule every 5 minutes
    scheduler.add_job(run_worker_cycle, 'interval', minutes=5, next_run_time=datetime.now())
    scheduler.start()
    
    # Keep the process alive
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker shutting down...")

if __name__ == "__main__":
    asyncio.run(main())
