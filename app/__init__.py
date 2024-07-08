import logging
from flask import Flask, request as req
from flask_assets import Environment, Bundle
from app.controllers import pages

def create_app(config_filename):
    app = Flask(__name__)
    app.config.from_object(config_filename)

    app.register_blueprint(pages.blueprint)

    # Initialize Flask-Assets
    assets = Environment(app)

    # Define the SASS bundle
    scss = Bundle('scss/main.scss', filters='libsass', output='dist/css/main.css')
    assets.register('scss_all', scss)

    app.logger.setLevel(logging.NOTSET)

    @app.after_request
    def log_response(resp):
        app.logger.info("{} {} {}\n{}".format(
            req.method, req.url, req.data, resp)
        )
        return resp

    # Log asset rebuild
    def rebuild_assets():
        app.logger.info('Rebuilding assets...')
        assets['scss_all'].urls()
        app.logger.info('Assets rebuilt successfully!')

    # Ensure assets are built before the first request
    @app.before_request
    def before_first_request():
        if not hasattr(app, 'assets_built'):
            rebuild_assets()
            app.assets_built = True

    app.rebuild_assets = rebuild_assets  # Attach the rebuild function to the app instance

    return app
