import os
import logging

from flask import Flask, request as req
from flask_wtf.csrf import CSRFProtect

from app.controllers import pages
from app.controllers.calendar import calendar
from app.controllers.upload import upload_bp
from app.db import db

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def create_app(config_filename=None):
    config_file_path = os.path.join(BASE_DIR, '..', 'config', f'{config_filename}.py')
    database_path = os.path.join(BASE_DIR, '..', 'database.db')

    app = Flask(__name__, instance_relative_config=False)
    app.config.from_mapping(
        FLASK_APP='app:create_app("development")',
        SECRET_KEY='1a3a5858d7695287ef65558467b24bf15cb19138c01f8d09',
        DATABASE=database_path,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{database_path}',
        CSRF_ENABLED=True
    )

    if os.path.exists(config_file_path):
        app.config.from_pyfile(config_file_path, silent=True)

    db.init_app(app)
    CSRFProtect(app)

    app.register_blueprint(pages.blueprint)
    app.register_blueprint(calendar.calendar_bp)
    app.register_blueprint(upload_bp)

    with app.app_context():
        db.create_all()

    app.logger.setLevel(logging.NOTSET)

    @app.after_request
    def log_response(resp):
        app.logger.info("{} {} {}\n{}".format(
            req.method, req.url, req.data, resp)
        )
        return resp

    return app