import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
from app import create_app

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

if __name__ == "__main__":
    app = create_app('config.development.settings')
    logging.basicConfig(level=logging.INFO)
    w = Watcher(app)
    w.run()
