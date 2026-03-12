from flask import Flask

from app.database.db import init_db
from app.routes.main_routes import main


def create_app():
    app = Flask(__name__)

    app.register_blueprint(main)
    init_db()

    return app
