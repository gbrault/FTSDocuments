import logging
import fts_config
import os
from flask import Flask,  g, redirect, url_for, Markup, current_app
from flask_appbuilder import AppBuilder, SQLA, Model, ModelView, CompactCRUDMixin
from flask_appbuilder.models.mixins import AuditMixin, FileColumn
from sqlalchemy import  (   event,
                            MetaData, 
                            Table,
                            Column,
                            Integer,
                            BigInteger,
                            String,
                            Text,
                            Date,
                            DateTime,
                            Float,
                            Boolean,
                            ForeignKeyConstraint,
                            Index,
                            UniqueConstraint,
                            Numeric)
from sqlalchemy.orm import relationship, Session      
from flask_appbuilder.filemanager import get_file_original_name 
from flask_appbuilder.models.sqla.interface import SQLAInterface

# LOGGING =======================================================================================================================

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logging.getLogger().setLevel(logging.DEBUG)

# APP ==========================================================================================================================

app = Flask(__name__)
app.config.from_object("fts_config")
schema = app.config['SCHEMA']
schema_fts = app.config['SCHEMA_FTS']
db = SQLA(app)
appbuilder = AppBuilder(app, db.session)
metadata_obj = db.metadata

# MODELS =======================================================================================================================

def represent(table,paths):
    repr = ""
    for path in paths:
        segments = path.split('.')
        ctable = table
        for p in segments:
            ctable = getattr(ctable,p)
        repr += str(ctable)+" "
    return repr.strip()

class Document(AuditMixin,Model):
    __bind_key__ = schema
    __tablename__ = 'document'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''Document table record unique id''')
    name = Column(String(150), nullable=False, comment='''Document name''')
    def __repr__(self):
        return f"{represent(self, ['name'])}"

class DocumentFiles(Model):
    __bind_key__ = schema
    __tablename__ = 'documentfiles'
    __table_args__ = (
        ForeignKeyConstraint(
            ['document_id'],
            ['document.id']
            ),
    )
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''DocumentFiles table's record unique id''')
    document_id = Column(Integer, nullable=False, comment='''''')
    file = Column(FileColumn, nullable=False,comment='''Document File''')
    description = Column(String(150), nullable=False, comment='''Document description''')
    document = relationship('Document')
    def __repr__(self):
        return f"{represent(self, ['file_name'])}"
    def download(self):
        return Markup(
            '<a href="'
            + url_for("DocumentFilesView.download", filename=str(self.file),as_attachment=0)
            + '" target="_blank">Download</a>'
        )
    def file_name(self):
        return get_file_original_name(str(self.file))

# listen for the 'after_insert' event
@event.listens_for(DocumentFiles, 'after_insert')
def receive_after_insert(mapper, connection, target):
    if not os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], target.file)):
        raise Exception('File not found: ' + target.value)
    pdf_to_documentsfilescontent(target)

# listen for the 'after_delete' event
@event.listens_for(DocumentFiles, 'after_delete')
def receive_after_insert(mapper, connection, target):
    if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], target.file)):
        raise Exception('File is found: ' + target.value)

# listen for the 'after_update' event
@event.listens_for(DocumentFiles, 'after_update')
def receive_after_update(mapper, connection, target):
    if not os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], target.file)):
        raise Exception('File not found: ' + target.value)

# VIEWS =======================================================================================================================

class DocumentFilesView(ModelView):
    datamodel = SQLAInterface(DocumentFiles)
    description_columns = {
         "id":"""DocumentFiles table's record unique id""",
         "document_id":"""""",
         "file":"""Document File""",
         "description":"""Document description"""
    }
    label_columns = {
        "file_name":"File Name",
        "download":"Download"
    }
    list_columns = ['file_name', 'download', 'description']
    show_columns = ['file_name', 'description', 'download' ]
    add_columns = ['file', 'description', 'document' ]
    edit_columns = ['file', 'description', 'document']

class DocumentView(CompactCRUDMixin,ModelView):
    datamodel = SQLAInterface(Document)
    description_columns = {
         "id":"""Document table record unique id""",
         "name":"""Document name"""
    }
    list_columns = ['name', 'created_by', 'changed_by', 'changed_on']
    add_columns = ['name']
    edit_columns = ['name']
    show_fieldsets = [
                      ("Info", {"fields": ["name"]}),
                      (
                          "Audit",
                          {
                              "fields": ["created_by", "created_on", "changed_by", "changed_on"],
                              "expanded": False,
                          },
                      ),]
    list_template = 'appbuilder/general/model/list.html'
    show_template = 'appbuilder/general/model/show_cascade.html'
    edit_template = 'appbuilder/general/model/edit_cascade.html'
    related_views = [
            DocumentFilesView
    ]

# FTS ==========================================================================================================================
from fts import *

# INIT =======================================================================================================================

# Create default useradmin
username = "admin"
firstname = "ad"
lastname = "min"
email = "admin@email.com"
password = "password"

FTS_DocumentFiles.__bind_key__ = schema_fts

db.create_all(bind=schema)
db.create_all(bind=schema_fts) # create the fts schema, needed by the fts5 virtual table

prepare_fts(appbuilder) # create the virtual table

db.create_all(bind=schema_fts) # create the appropriate models and views used for fts

with app.app_context():
    user = current_app.appbuilder.sm.find_user(username=username)
    if user:
        logging.info("User already exists")
    else:
        logging.info("Creating user")
        user = current_app.appbuilder.sm.add_user(
            username=username,
            first_name=firstname,
            last_name=lastname,
            email=email,
            role=current_app.appbuilder.sm.find_role("Admin"),
            password=password,
        )
        db.session.commit()    

appbuilder.add_view(DocumentView,"Documents",icon="fa-database",category="Documents")
appbuilder.add_view_no_menu(DocumentFilesView)
fts_menus(appbuilder)

# EVENT LISTENERS =============================================================================================================
@event.listens_for(appbuilder.session, "do_orm_execute")
def _do_orm_execute(orm_execute_state):
    if orm_execute_state.is_select:
        # add populate_existing for all SELECT statements
        for table in orm_execute_state.statement.froms:
            if table.name == 'ftsdocumentsfilescontent_fts':
                break
