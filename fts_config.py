import os
SCHEMA="FTPG"
SCHEMA_FTS="FTPG_FTS"
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__),"fts-data"))
dburl = "sqlite:///"+os.path.join(basedir, f"{SCHEMA}.db")
dbftsurl = "sqlite:///"+os.path.join(basedir, f"{SCHEMA_FTS}.db")
SQLALCHEMY_DATABASE_URI = dburl
SQLALCHEMY_BINDS = {
    f"{SCHEMA}": dburl,
    f"{SCHEMA_FTS}": dbftsurl
}
CSRF_ENABLED = True
SECRET_KEY = "\2\1thisismyscretkey\1\2\e\y\y\h"
UPLOAD_FOLDER = os.path.join(basedir,"fts-data")
SQLALCHEMY_TRACK_MODIFICATIONS = False

max_workers = 2 # the sqlite database is not thread safe
