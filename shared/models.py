from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    ruc = Column(String(11), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    credentials = relationship("Credential", back_populates="company", cascade="all, delete-orphan")
    executions = relationship("Execution", back_populates="company")

class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    sol_user = Column(String(50), nullable=False)
    sol_password_encrypted = Column(Text, nullable=False) # Fernet encrypted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="credentials")

class Execution(Base):
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(ExecutionStatus), default=ExecutionStatus.PENDING)
    account_checked_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(String(255), nullable=True)

    company = relationship("Company", back_populates="executions")
    notifications = relationship("Notification", back_populates="execution")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=False)
    external_reference = Column(String(100), unique=True, nullable=False) # SUNAT ID
    title = Column(String(255))
    content_summary = Column(Text)
    received_at = Column(DateTime)
    processed_at = Column(DateTime, default=datetime.utcnow)

    execution = relationship("Execution", back_populates="notifications")
    documents = relationship("Document", back_populates="notification")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=False)
    filename = Column(String(255))
    file_path = Column(String(255))
    file_hash = Column(String(64)) # SHA-256 for idempotency
    created_at = Column(DateTime, default=datetime.utcnow)

    notification = relationship("Notification", back_populates="documents")

class WorkerStatus(Base):
    __tablename__ = "worker_status"

    id = Column(Integer, primary_key=True)
    worker_name = Column(String(50), unique=True)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    current_job = Column(String(255), nullable=True)
    state = Column(JSON, nullable=True) # Any extra metrics
    jobs_processed = Column(Integer, default=0)

class ErrorLog(Base):
    __tablename__ = "errors"

    id = Column(Integer, primary_key=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=True)
    error_type = Column(String(100))
    message = Column(Text)
    stack_trace = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmailDelivery(Base):
    __tablename__ = "email_deliveries"

    id = Column(Integer, primary_key=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=False)
    recipient = Column(String(255))
    subject = Column(String(255))
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50)) # e.g., "sent", "failed"
