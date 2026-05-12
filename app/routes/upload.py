import json
import logging
import uuid
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from app.services.csv_processor import parse_csv, profile_csv

logger = logging.getLogger(__name__)
upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {"csv"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_bp.route("/upload", methods=["GET"])
def upload_page():
    return render_template("upload.html", active_tab="upload")


@upload_bp.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        flash("No file part in the request.", "error")
        return redirect(url_for("upload.upload_page"))

    file = request.files["file"]
    target_table = request.form.get("target_table", "").strip().lower()

    if not file or file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("upload.upload_page"))

    if not _allowed_file(file.filename):
        flash("Only CSV files are accepted.", "error")
        return redirect(url_for("upload.upload_page"))

    if not target_table:
        flash("Target table name is required.", "error")
        return redirect(url_for("upload.upload_page"))

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)

    file_uuid = str(uuid.uuid4())
    safe_name = secure_filename(file.filename)
    csv_path = upload_folder / f"{file_uuid}.csv"
    file.save(csv_path)

    try:
        df = parse_csv(csv_path)
        profile = profile_csv(df)
    except Exception as exc:
        logger.error("Failed to parse CSV %s: %s", csv_path, exc)
        csv_path.unlink(missing_ok=True)
        flash(f"CSV parsing failed: {exc}", "error")
        return redirect(url_for("upload.upload_page"))

    profile_path = upload_folder / f"{file_uuid}_profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    session["upload_uuid"] = file_uuid
    session["upload_filename"] = safe_name
    session["upload_target_table"] = target_table

    return redirect(url_for("explore.explore_page"))
