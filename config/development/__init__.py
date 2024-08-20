import os

# database 
DEBUG = True
TREADED = True
SECRET_KEY = 'b3V6Tw0aHrtP9q7tUMxSXQKMjHmcdFKa'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', 5000))
