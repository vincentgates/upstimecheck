import os
import logging

from flask import Flask, request as req

from app.controllers import pages
from app.controllers.authentication import authentication
from app.controllers.calendar import calendar

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def create_app(config_filename=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        FLASK_APP='run.py',
        SECRET_KEY = '1a3a5858d7695287ef65558467b24bf15cb19138c01f8d09',  # Replace with the generated key
        # Database
        DATABASE = os.path.join(os.getenv('INSTANCE_PATH', ''), '../database.db'),
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, '../database.db')}',
        CSRF_ENABLED = True
    )

    if config_filename is None:
        # python run.py
        app.config.from_pyfile('../config/development.py', silent=True)
    else:
        # flask run
        app.config.from_mapping(config_filename)

    
    app.register_blueprint(pages.blueprint)
    app.register_blueprint(authentication.authentication_bp)
    app.register_blueprint(calendar.calendar_bp)

    app.logger.setLevel(logging.NOTSET)

    @app.after_request
    def log_response(resp):
        app.logger.info("{} {} {}\n{}".format(
            req.method, req.url, req.data, resp)
        )
        return resp

    return app
