import logging

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from app.extensions import db
from app.models.job import ETLJob
from app.services.scheduler import register_job, trigger_job_now, unregister_job

logger = logging.getLogger(__name__)
jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("/jobs", methods=["GET"])
def jobs_page():
    jobs = ETLJob.query.order_by(ETLJob.created_at.desc()).all()
    return render_template("jobs.html", active_tab="jobs", jobs=jobs)


@jobs_bp.route("/jobs/create", methods=["POST"])
def create_job():
    process_name = request.form.get("process_name", "").strip()
    schedule = request.form.get("schedule", "").strip()
    source_path = request.form.get("source_path", "").strip()
    target_table = request.form.get("target_table", "").strip()

    if not process_name or not schedule:
        flash("Process name and schedule are required.", "error")
        return redirect(url_for("jobs.jobs_page"))

    job = ETLJob(
        process_name=process_name,
        schedule=schedule,
        source_path=source_path or None,
        target_table=target_table or None,
        status="idle",
    )
    db.session.add(job)
    db.session.commit()

    if source_path and target_table:
        register_job(current_app._get_current_object(), job)

    flash(f"Job '{process_name}' created.", "success")
    return redirect(url_for("jobs.jobs_page"))


@jobs_bp.route("/jobs/<int:job_id>/trigger", methods=["POST"])
def trigger_job(job_id: int):
    job = db.session.get(ETLJob, job_id)
    if not job:
        return jsonify({"error": "Job not found", "status": 404}), 404

    if not job.source_path or not job.target_table:
        return jsonify({"error": "Job has no source path or target table configured.", "status": 400}), 400

    trigger_job_now(current_app._get_current_object(), job_id)
    return jsonify({"success": True, "message": f"Job '{job.process_name}' triggered."})


@jobs_bp.route("/jobs/<int:job_id>/delete", methods=["POST"])
def delete_job(job_id: int):
    job = db.session.get(ETLJob, job_id)
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("jobs.jobs_page"))

    unregister_job(job_id)
    db.session.delete(job)
    db.session.commit()
    flash(f"Job '{job.process_name}' deleted.", "success")
    return redirect(url_for("jobs.jobs_page"))
