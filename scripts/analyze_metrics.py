import sqlalchemy
from sqlalchemy.orm import sessionmaker
from shared.models import Execution, ExecutionStatus, ErrorLog
from datetime import datetime, timedelta
import os

# Setup database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@osorio-db:5432/osorio_platform")
engine = sqlalchemy.create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def analyze():
    db = SessionLocal()
    
    # 1. Overall Stats
    total = db.query(Execution).count()
    success = db.query(Execution).filter(Execution.status == ExecutionStatus.SUCCESS).count()
    failed = db.query(Execution).filter(Execution.status == ExecutionStatus.FAILED).count()
    
    success_rate = (success / total * 100) if total > 0 else 0
    
    # 2. Avg Duration
    durations = []
    executions = db.query(Execution).filter(Execution.finished_at != None).all()
    for ex in executions:
        durations.append((ex.finished_at - ex.started_at).total_seconds())
    
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # 3. Error Analysis
    error_counts = {}
    
    # Check typed errors
    typed_errors = db.query(ErrorLog.error_type, sqlalchemy.func.count(ErrorLog.id)).group_by(ErrorLog.error_type).all()
    for etype, count in typed_errors:
        error_counts[etype] = count
        
    # Analyze old untyped errors by message
    untyped_failures = db.query(Execution).filter(Execution.status == ExecutionStatus.FAILED).all()
    for fail in untyped_failures:
        # Check if it already has a typed log
        has_log = db.query(ErrorLog).filter(ErrorLog.execution_id == fail.id).first()
        if not has_log:
            msg = fail.error_message or ""
            etype = "UNKNOWN"
            if "iframeApplication" in msg: etype = "IFRAME_TIMEOUT"
            elif "Buzón Electrónico" in msg: etype = "LOGIN_REDIRECT_TIMEOUT"
            elif "Timeout" in msg: etype = "NETWORK_TIMEOUT"
            elif "selector" in msg.lower(): etype = "SELECTOR_NOT_FOUND"
            
            error_counts[etype] = error_counts.get(etype, 0) + 1

    print("\n" + "="*40)
    print("      SUNAT AUTOMATION METRICS REPORT")
    print("="*40)
    print(f"Total Executions: {total}")
    print(f"Success Rate:     {success_rate:.1f}% ({success}/{total})")
    print(f"Failure Rate:     {100-success_rate:.1f}% ({failed}/{total})")
    print(f"Avg Cycle Time:   {avg_duration:.2f}s")
    print("-"*40)
    print("Failure Root Causes:")
    for etype, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
        print(f" - {etype:25}: {count} ({count/failed*100:.1f}%)")
    print("="*40 + "\n")

    db.close()

if __name__ == "__main__":
    analyze()
