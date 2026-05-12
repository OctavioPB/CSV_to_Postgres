import logging

from flask import Blueprint, current_app, render_template, request
from sqlalchemy import MetaData, Table, create_engine, func, inspect, select

logger = logging.getLogger(__name__)
data_bp = Blueprint("data", __name__)

PAGE_SIZE = 50


def _get_engine():
    return create_engine(current_app.config["SQLALCHEMY_DATABASE_URI"])


@data_bp.route("/data", methods=["GET"])
def data_page():
    selected_table = request.args.get("table", "").strip()
    page = max(1, int(request.args.get("page", 1) or 1))

    engine = _get_engine()
    inspector = inspect(engine)
    all_tables = sorted(inspector.get_table_names())

    columns: list[str] = []
    rows: list[list] = []
    total_rows = 0
    total_pages = 1
    error: str | None = None

    if selected_table and selected_table in all_tables:
        try:
            metadata = MetaData()
            table = Table(selected_table, metadata, autoload_with=engine)
            offset = (page - 1) * PAGE_SIZE

            with engine.connect() as conn:
                total_rows = conn.execute(select(func.count()).select_from(table)).scalar() or 0
                result = conn.execute(select(table).limit(PAGE_SIZE).offset(offset))
                columns = list(result.keys())
                rows = [list(row) for row in result]

            total_pages = max(1, (total_rows + PAGE_SIZE - 1) // PAGE_SIZE)
        except Exception as exc:
            logger.error("Failed to query table %s: %s", selected_table, exc)
            error = str(exc)

    return render_template(
        "data.html",
        active_tab="data",
        all_tables=all_tables,
        selected_table=selected_table,
        columns=columns,
        rows=rows,
        total_rows=total_rows,
        page=page,
        total_pages=total_pages,
        page_size=PAGE_SIZE,
        error=error,
    )
