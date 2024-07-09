import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

# database 
DEBUG = True
SECRET_KEY = 'my precious'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
HOST = 'localhost'
PORT = int(os.environ.get('PORT', 5000))


class Watcher:
    DIRECTORY_TO_WATCH = "app/static/scss"

    def __init__(self, app):
        self.observer = Observer()
        self.app = app

    def run(self):
        event_handler = Handler(self.app)
        self.observer.schedule(event_handler, self.DIRECTORY_TO_WATCH, recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            self.observer.stop()
            print("Observer Stopped")

        self.observer.join()

class Handler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)

    def on_modified(self, event):
        if event.src_path.endswith('.scss'):
            self.logger.info(f'{event.src_path} has been modified. Rebuilding assets...')
            with self.app.app_context():
                try:
                    self.app.rebuild_assets()
                    self.logger.info('Assets rebuilt successfully!')
                except Exception as e:
                    self.logger.error(f'Error rebuilding assets: {e}')