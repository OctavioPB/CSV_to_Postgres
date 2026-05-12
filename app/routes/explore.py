import json
import logging
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
from sqlalchemy import create_engine

from app.extensions import db
from app.models.upload_log import UploadLog
from app.services.csv_processor import parse_csv
from app.services.db_manager import (
    build_column_map,
    bulk_insert,
    coerce_dataframe,
    create_table_if_not_exists,
)

logger = logging.getLogger(__name__)
explore_bp = Blueprint("explore", __name__)

VALID_TYPES = {"int64", "float64", "datetime", "bool", "str"}


@explore_bp.route("/explore", methods=["GET"])
def explore_page():
    file_uuid = session.get("upload_uuid")
    if not file_uuid:
        flash("Upload a CSV file first.", "info")
        return redirect(url_for("upload.upload_page"))

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    profile_path = upload_folder / f"{file_uuid}_profile.json"

    if not profile_path.exists():
        flash("Session data expired. Please re-upload.", "error")
        session.pop("upload_uuid", None)
        return redirect(url_for("upload.upload_page"))

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    return render_template(
        "explore.html",
        active_tab="explore",
        profile=profile,
        filename=session.get("upload_filename", ""),
        target_table=session.get("upload_target_table", ""),
        result=None,
    )


@explore_bp.route("/explore/confirm", methods=["POST"])
def explore_confirm():
    file_uuid = session.get("upload_uuid")
    if not file_uuid:
        flash("Session expired. Please re-upload.", "error")
        return redirect(url_for("upload.upload_page"))

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    csv_path = upload_folder / f"{file_uuid}.csv"
    profile_path = upload_folder / f"{file_uuid}_profile.json"

    if not csv_path.exists():
        flash("Upload file not found. Please re-upload.", "error")
        return redirect(url_for("upload.upload_page"))

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    target_table = request.form.get("target_table", session.get("upload_target_table", ""))
    filename = session.get("upload_filename", csv_path.name)

    type_overrides: dict[str, str] = {}
    for col in profile["columns"]:
        form_key = f"type_{col['name']}"
        override = request.form.get(form_key, "").strip()
        if override in VALID_TYPES:
            type_overrides[col["name"]] = override

    try:
        df = parse_csv(csv_path)
        col_map = build_column_map(profile["columns"], type_overrides)
        engine = create_engine(current_app.config["SQLALCHEMY_DATABASE_URI"])
        table = create_table_if_not_exists(engine, target_table, col_map)
        coerced = coerce_dataframe(df, col_map)
        rows_inserted, rows_failed = bulk_insert(engine, table, coerced)
        error_message = None
    except Exception as exc:
        logger.error("Insert failed for table %s: %s", target_table, exc, exc_info=True)
        rows_inserted = 0
        rows_failed = 0
        error_message = str(exc)

    log = UploadLog(
        filename=filename,
        target_table=target_table,
        rows_inserted=rows_inserted,
        rows_failed=rows_failed,
        error_message=error_message,
        triggered_by="manual",
    )
    db.session.add(log)
    db.session.commit()

    result = {
        "rows_inserted": rows_inserted,
        "rows_failed": rows_failed,
        "target_table": target_table,
        "error": error_message,
    }

    return render_template(
        "explore.html",
        active_tab="explore",
        profile=profile,
        filename=filename,
        target_table=target_table,
        result=result,
    )
