import os

# The path to the database. It's set to be located in the instance folder by default.
DATABASE = os.path.join(os.getenv('INSTANCE_PATH', ''), 'flaskr.sqlite')

# Example of other configuration settings:
DEBUG = False  # Disable debug mode in production
TESTING = False  # Not in testing mode