from datetime import datetime
from app.extensions import db


class UploadLog(db.Model):
    __tablename__ = "upload_logs"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    target_table = db.Column(db.String(120))
    rows_inserted = db.Column(db.Integer, default=0)
    rows_failed = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    triggered_by = db.Column(db.String(40))  # "manual" | "scheduler"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
