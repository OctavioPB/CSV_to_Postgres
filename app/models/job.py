from datetime import datetime
from app.extensions import db


class ETLJob(db.Model):
    __tablename__ = "etl_jobs"

    id = db.Column(db.Integer, primary_key=True)
    process_name = db.Column(db.String(120), nullable=False)
    schedule = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default="idle")
    last_run = db.Column(db.DateTime, nullable=True)
    source_path = db.Column(db.String(255), nullable=True)
    target_table = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "process_name": self.process_name,
            "schedule": self.schedule,
            "status": self.status,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "source_path": self.source_path,
            "target_table": self.target_table,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
