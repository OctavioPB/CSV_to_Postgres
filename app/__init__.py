import logging
from flask import Flask, redirect, url_for
from app.config import Config
from app.extensions import db, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes.upload import upload_bp
    from app.routes.explore import explore_bp
    from app.routes.jobs import jobs_bp
    from app.routes.data import data_bp

    app.register_blueprint(upload_bp)
    app.register_blueprint(explore_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(data_bp)

    @app.route("/")
    def index():
        return redirect(url_for("upload.upload_page"))

    if not app.config.get("TESTING"):
        with app.app_context():
            from app.services.scheduler import init_scheduler
            init_scheduler(app)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    return app
