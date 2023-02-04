"""Full Text Shearch for Flask App Builder

Summary: This module enables full text search for a table in a database.

"""
from concurrent.futures import ThreadPoolExecutor
import time
from sqlalchemy import  (   create_engine,
                            event,
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
from flask_appbuilder import AppBuilder, SQLA, Model, ModelView, CompactCRUDMixin
from flask_appbuilder.models.mixins import AuditMixin, FileColumn
import fts_config
from sqlalchemy.orm import relationship
from flask_appbuilder.models.sqla.interface import SQLAInterface
from sqlalchemy.orm import sessionmaker
import os
from flask_appbuilder.filemanager import get_file_original_name
import types
from flask import g, redirect, url_for, Markup, current_app, flash
import sqlite3
from sqlite3 import Connection
from typing import List
from flask_appbuilder.models.decorators import renders
import re
import logging
import os
import datetime

logger = logging.getLogger(__name__)

__version__ = "0.0.1"
__author__ = "Gilbert Brault"
__email__ = "gbrault@seadev.org"
__license__ = "MIT"
__status__ = "Development"

def convert_pdf_to_html(path):
    from io import StringIO
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.converter import HTMLConverter
    from pdfminer.layout import LAParams
    from pdfminer.pdfpage import PDFPage
    from pdfminer.image import ImageWriter
    logger = logging.getLogger("pdfminer")
    logger.setLevel(logging.ERROR)
    manager = PDFResourceManager()
    output = StringIO()
    outdir = path.replace(".pdf","")
    imagewriter = None # imagewriter=ImageWriter(outdir)
    converter = HTMLConverter(manager, output, laparams=LAParams(), codec=None,imagewriter=imagewriter,showpageno=False)
    interpreter = PDFPageInterpreter(manager, converter)

    with open(path, 'rb') as fh:
        for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
            interpreter.process_page(page)

    return output.getvalue()

def enable_fts( db: Connection=None, 
                content: str='',
                fts: str='',
                columns: List[str]=[], 
                col_attrs: dict={}):
    """Enable full text search for a table in a database.
    Args:
        db (Connection): Database connection.
        table (str): Name of the table to enable full text search.
        columns (List[str]): List of columns to enable full text search.
        col_attrs (dict): Dictionary of column attributes.
    """
    global FTS_LEAN_VIEW, FTS_LEAN_VIEWView
    # Specifics ==================================================================================================================
            
    column_list = ','.join(f'`{c}`' for c in columns)
    column_list_wattrs = ','.join(f'`{c}` {col_attrs[c] if c in col_attrs else ""}' for c in columns)
    table = content
    fts_table = fts
    sql_script_1 = '''
        CREATE VIRTUAL TABLE IF NOT EXISTS `{fts_table}` USING fts5
        (
            {column_list_wattrs},
            content=`{table}`
        )'''.format(
        fts_table=fts_table,
        table=table,
        column_list_wattrs=column_list_wattrs
    )
    db.executescript(sql_script_1)

    #cursor = db.cursor()
    #cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    #tables = cursor.fetchall()
    #print(tables)

    sql_script_2 ='''
        CREATE TRIGGER IF NOT EXISTS `{fts_table}_insert` AFTER INSERT ON `{table}`
        BEGIN
            INSERT INTO `{fts_table}` (rowid, {column_list}) VALUES (new.rowid, {new_columns});
        END;
        CREATE TRIGGER IF NOT EXISTS `{fts_table}_delete` AFTER DELETE ON `{table}`
        BEGIN
            INSERT INTO `{fts_table}` (`{fts_table}`, rowid, {column_list}) VALUES ('delete', old.rowid, {old_columns});
        END;
        CREATE TRIGGER IF NOT EXISTS `{table}_fts_update` AFTER UPDATE ON `{table}`
        BEGIN
            INSERT INTO `{fts_table}` (`{table}_fts`, rowid, {column_list}) VALUES ('delete', old.rowid, {old_columns});
            INSERT INTO `{fts_table}` (rowid, {column_list}) VALUES (new.rowid, {new_columns});
        END;
    '''.format(
        fts_table=fts_table,
        table=table,
        column_list=column_list,
        new_columns=','.join(f'new.`{c}`' for c in columns),
        old_columns=','.join(f'old.`{c}`' for c in columns),
    )

    db.executescript(sql_script_2)

    from fts_models_views import FTS_LEAN_VIEW, FTS_LEAN_VIEWView


def represent(table,paths):
    repr = ""
    for path in paths:
        segments = path.split('.')
        ctable = table
        for p in segments:
            ctable = getattr(ctable,p)
        if type(ctable) == types.MethodType:
            repr += ctable().replace("'","''")+" "
        else:
            repr += str(ctable).replace("'","''")+" "
    return repr.strip()

# Models ===========================================================================================================================

class FTS_DocumentFiles(Model):
    __bind_key__ = fts_config.SCHEMA_FTS
    __tablename__ = 'ftsdocumentfiles'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''DocumentFiles table's record unique id''')
    file = Column(FileColumn, nullable=False,comment='''Document File name''')
    # start index timestamp
    start_index = Column(DateTime, nullable=False, comment='''Start index timestamp''')
    # end index timestamp
    end_index = Column(DateTime, nullable=False, comment='''End index timestamp''')
    def __repr__(self):
        return f"{represent(self, ['file_name'])}"  
    def file_name(self):
        return get_file_original_name(str(self.file))
    def download(self):
        return Markup(
            '<a href="'
            + url_for("FTS_DocumentFilesView.download", filename=str(self.file))
            + f'">{self.file_name()}</a>'
        )
    def indexing_duration(self):
        return self.end_index - self.start_index

class FTS_DocumentsFilesDivs(Model):
    __bind_key__ = fts_config.SCHEMA_FTS
    __tablename__ = 'ftsdocumentsfilesdivs'
    __table_args__ = (
        ForeignKeyConstraint(
            ['document_id'],
            ['ftsdocumentfiles.id']
            ),
    )    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''DocumentsFilesDivs table's record unique id''')
    document_id = Column(Integer, nullable=False, comment='''document unique id (table FTS_DocumentFiles)''')
    left = Column(Float, nullable=False, comment='''x left top''')
    top = Column(Float, nullable=False, comment='''y left top''')
    width = Column(Float, nullable=False, comment='''x right bottom''')
    height = Column(Float, nullable=False, comment='''y right bottom''')
    page = Column(Integer, nullable=False, comment='''Page number of the block''')
    documentfiles = relationship('FTS_DocumentFiles', backref='ftsdocumentsfilesdivs', foreign_keys=[document_id])

class FTS_DocumentsFilesSpans(Model):
    __bind_key__ = fts_config.SCHEMA_FTS
    __tablename__ = 'ftsdocumentsfilesspans'
    __table_args__ = (
        ForeignKeyConstraint(
            ['div_id'],
            ['ftsdocumentsfilesdivs.id']
            ),
    )    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''DocumentsFilesContent table's record unique id''')
    div_id = Column(Integer, nullable=False, comment='''DB unique record identifier of the document''')
    font_family = Column(String(255), nullable=False, comment='''Font name''')
    font_size = Column(Float, nullable=False, comment='''Font size''')
    text = Column(Text, nullable=False, comment='''Text''')
    documentfilesdivs = relationship('FTS_DocumentsFilesDivs', backref='ftsdocumentsfilesspans', foreign_keys=[div_id])
          

# Views ===========================================================================================================================================

class FTS_DocumentFilesView(ModelView):
    datamodel = SQLAInterface(FTS_DocumentFiles)
    list_columns = ['id', 'download','start_index','indexing_duration']
    label_columns = dict(
        id = 'Id',
        file = 'File',
        start_index = 'Start Index',
        end_index = 'End Index',
        indexing_duration = 'Indexing Duration'
        )
    show_columns = ['id', 'file','start_index','end_index','indexing_duration']
    edit_columns = ['file']
    add_columns = [ 'file']

class FTS_DocumentsFilesDivsView(ModelView):
    datamodel = SQLAInterface(FTS_DocumentsFilesDivs)
    label_columns = dict(
        id = 'Id',
        document_id = 'Document Id',
        left = 'Left',
        top = 'Top',
        width = 'Width',
        height = 'Height',
        page = 'Page'
        )
    description_columns = dict(
        id = 'DocumentFilesContent table\'s record unique id',
        document_id = 'document identifier (table FTS_DocumentFiles)',
        left = 'x left top',
        top = 'y left top',
        width = 'div width',
        height = 'div height',
        page = 'Page number of the block'
        )
    list_columns = ['document_id', 'page', 'left', 'top', 'width', 'height']
    show_columns = ['id', 'document_id', 'page', 'left', 'top', 'width', 'height']
    add_columns =  ['id', 'document_id', 'page', 'left', 'top', 'width', 'height']
    edit_columns =  ['id', 'document_id', 'page', 'left', 'top', 'width', 'height']

class FTS_DocumentsFilesSpansView(ModelView):
    datamodel = SQLAInterface(FTS_DocumentsFilesSpans)
    label_columns = dict(
        id = 'Id',
        div_id = 'Div Id',
        font_family = 'Font Family',
        font_size = 'Font Size',
        text = 'Text'
        )
    description_columns = dict(
        id = 'DocumentsFilesContent table\'s record unique id',
        div_id = 'div identifier (table FTS_DocumentsFilesDivs)',
        font_family = 'Font name',
        font_size = 'Font size',
        text = 'Text'
        )
    list_columns = ['font_family', 'font_size', 'text']
    show_columns = ['id', 'div_id', 'font_family', 'font_size', 'text']
    add_columns =  ['id', 'div_id', 'font_family', 'font_size', 'text']
    edit_columns =  ['id', 'div_id', 'font_family', 'font_size', 'text']

# Functions needing Models ===========================================================================================================================
def convert_pdf_to_records(session, file):
    """Save the converted pdf files to the database

    :param session: SQLAlchemy session
    :param path: path to the pdf file
    :return: None

    Summary:
    1. convert pdf to html
    2. Process the document to create records into the database
        - save the document to the database
        - find the page breaker template
        - In between each page_breaker
            - find the divs
            - find the spans
            - save the divs and spans to the database
    """
    from bs4 import BeautifulSoup
    import re
    path = os.path.join(fts_config.UPLOAD_FOLDER, file)
    # convert pdf to html  ===================================================================================================
    logger.info("Saving the document to the database")
    now = datetime.datetime.now()
    fts_documentfiles = FTS_DocumentFiles(file=file, start_index=now, end_index=now)
    session.add(fts_documentfiles)
    session.commit()    
    try:
        logger.info("Converting pdf to html")
        html_doc = convert_pdf_to_html(path)
        logger.info("Converted pdf to html")
    except Exception as e:
        logger.error("Error converting pdf to html: ", e)
        return
    # save the document to the database
    soup = BeautifulSoup(html_doc, 'html.parser')
    # find the first span with style width and height: it is the page breaker template
    body = soup.find("body")
    span = body.find("span") # this is the template
    # parse the style attribute of the span for the height and width
    # style example is style="position:absolute; border: gray 1px solid; left:0px; top:50px; width:595px; height:842px;"
    # get the width and height
    style = span["style"]
    t_width = re.search("width:\s*(\d+)px", style).group(1)
    t_page_height = re.search("height:\s*(\d+)px", style).group(1)
    # code to identify the page breakers using beautifull soup
    # the page breaker spans are the spans with the same height and width as the template
    page = 1  # prepare the page number for the page records
    div_number = 1 # prepare the div number for the div records
    for span in body.find_all("span"):
        # parse the style attribute of the span for the height and width
        # style example is style="position:absolute; border: gray 1px solid; left:0px; top:50px; width:595px; height:842px;"
        # get the width and height
        style = span["style"]
        if "width" in style:
            width = re.search("width:\s*(\d+)px", style).group(1)
            height = re.search("height:\s*(\d+)px", style).group(1)
            if width == t_width and height == t_page_height:
                # the page_records divs are all the divs embedding spans
                # we can find the page_records divs, iterating from the next_sibilings of the page breaker, until the next page breaker (a span with the same height and width as the template)
                # the page_records divs are all the divs embedding spans
                starter = span.find_next_sibling()
                while True:
                    if starter is None:
                        break
                    # if the next sibling is a span with the same height and width as the template, we stop
                    if starter.name == "span":
                        # parse the style attribute of the span for the height and width
                        # style example is style="position:absolute; border: gray 1px solid; left:0px; top:50px; width:595px; height:842px;"
                        # get the width and height
                        style = starter["style"]
                        if "width" in style:
                            width = re.search("width:(\d+)px", style).group(1)
                            height = re.search("height:(\d+)px", style).group(1)
                            if width == t_width and height == t_page_height:
                                break
                    # if the next sibling is a div, we add it to the page_records
                    if starter.name == "div":
                        # if the div has embedded spans, we add it to the page_records
                        # get the spans
                        spans = starter.find_all("span")
                        if len(spans) > 0:
                            # parse the style attribute of the div for the height and width, top and left
                            # style="position:absolute; border: textbox 1px solid; writing-mode:lr-tb; left:325px; top:187px; width:223px; height:56px;"
                            style = starter["style"]
                            width = re.search("width:\s*(\d+)px", style).group(1)
                            height = re.search("height:\s*(\d+)px", style).group(1)
                            top = re.search("top:\s*(\d+)px", style).group(1)
                            left = re.search("left:\s*(\d+)px", style).group(1)
                            # save the page_record to the database
                            page_record = FTS_DocumentsFilesDivs(
                                page=page,
                                width=width,
                                height=height,
                                top=top,
                                left=left,
                                document_id=fts_documentfiles.id
                            )
                            session.add(page_record)
                            session.commit()
                            # add the spans to the page_records_spans
                            for span in spans:
                                # add a reference to the page_record
                                span.page_record = starter
                                span.div_number = div_number
                                div_number += 1
                                # parse the style attribute of the span for the font-size, font-family
                                # style="font-family: Arial-BoldMT; font-size:17px"
                                style = span["style"]
                                font_size = re.search("font-size:\s*(\d+)px", style).group(1)
                                font_family = re.search("font-family:\s*(\w+)", style).group(1)
                                # save the page_record_span to the database
                                try:
                                    page_record_span = FTS_DocumentsFilesSpans(
                                        font_size=font_size,
                                        font_family=font_family,
                                        text=span.get_text(),
                                        div_id=page_record.id)
                                    session.add(page_record_span)
                                    session.commit()
                                except Exception as e:
                                    logger.error("Error saving page_record_span: {}".format(e))
                    starter = starter.find_next_sibling()
                page += 1
    # update the document record
    now = datetime.datetime.now()
    fts_documentfiles.end_index=now
    session.commit()
    logger.info("Document {} indexed".format(fts_documentfiles.id))

# Menu ===========================================================================================================================================
def fts_menus(appbuilder):
    appbuilder.add_view(FTS_DocumentFilesView,"DocumentsFiles",icon="fa-file",category="Full_Text_Search")
    appbuilder.add_view(FTS_DocumentsFilesDivsView,"DocumentsFilesDivs",icon="fa-search",category="Full_Text_Search")
    appbuilder.add_view(FTS_DocumentsFilesSpansView,"DocumentsFilesSpans",icon="fa-search",category="Full_Text_Search")
    appbuilder.add_view(FTS_LEAN_VIEWView,"Documents Full Text Search",icon="fa-binoculars",category="Documents")

# FTSSearch ===========================================================================================================================================

# implement a threaded version of document indexing
# a tasklist is created and each task is a document to index or delete
# the tasklist is processed by a threadpool
# the threadpool is created with a maximum number of threads
# the threadpool is created with a maximum number of tasks in the queue

class FTSSearch:
    def __init__(self, appbuilder):
        self.appbuilder = appbuilder
        self.tasklist = []
        self.threadpool = ThreadPoolExecutor(max_workers=fts_config.max_workers)
        self.threadpool.submit(self.process_tasklist)

    def process_tasklist(self):
        while True:
            if len(self.tasklist) > 0:
                task = self.tasklist.pop(0) # first in first out
                if task['action'] == 'index':
                    self.threadpool.submit(pdf_to_documentsfilescontent, task['documentfiles'])
                if task['action'] == 'delete':
                    self.threadpool.submit(pdf_delete, task['documentfiles'])
            else:
                time.sleep(1)

    def index(self, documentfiles):
        # check if request already in tasklist
        for task in self.tasklist:
            if task['action'] == 'index' and task['documentfiles'] == documentfiles.file:
                self.appbuilder.send_alert('Document already in tasklist for indexing',"alert-warning")
                return
        # check if the document is already indexed and flash a message and return if it is
        file = self.appbuilder.session.query(FTS_DocumentFiles).filter(FTS_DocumentFiles.file == documentfiles.file).all()
        if file is not None and len(file) > 0:
            if file[0].end_index == file[0].start_index:
                self.appbuilder.send_alert('Document is indexing wait till end of indexing','alert-warning')
                return
            else:
                self.appbuilder.send_alert('Reindexing the Document','alert-info')
                # reindexing the document, so delete the document index
                self.tasklist.append({'action': 'delete', 'documentfiles': documentfiles.file})
                # add the document to the tasklist for indexing
                self.tasklist.append({'action': 'index', 'documentfiles': documentfiles.file})
                return
        # add the document to the tasklist for indexing
        self.tasklist.append({'action': 'index', 'documentfiles': documentfiles.file})
        self.appbuilder.send_alert('Document added to tasklist for indexing','alert-info')

    def delete(self, documentfiles):
        # check if request already in tasklist
        for task in self.tasklist:
            if task['action'] == 'delete' and task['documentfiles'] == documentfiles.file:
                self.appbuilder.send_alert('Document already in tasklist for deleting','alert-warning')
                return
        doc = self.appbuilder.session.query(FTS_DocumentFiles).filter(FTS_DocumentFiles.file == documentfiles.file).all()
        if doc is not None and len(doc) > 0:
            self.tasklist.append({'action': 'delete', 'documentfiles': doc[0].id})

def pdf_delete(id):
    engine = create_engine(fts_config.dbftsurl)
    Session = sessionmaker(engine)
    with Session() as session:
        # find the FTS_Documents Files with the id
        fts_document = session.query(FTS_DocumentFiles).filter(FTS_DocumentFiles.id == id).first()
        # for each FTS_DocumentsFiles find all FTS_DocumentsFilesDivs
        fts_documentsfiles = session.query(FTS_DocumentsFilesDivs).filter(FTS_DocumentsFilesDivs.document_id == id).all()
        # find all FTS_DocumentsFilesSpans with the div_id
        for fts_documentsfile in fts_documentsfiles:
            fts_documentsfilesspans = session.query(FTS_DocumentsFilesSpans).filter(FTS_DocumentsFilesSpans.div_id == fts_documentsfile.id).all()
            # delete all FTS_DocumentsFilesSpans
            for fts_documentsfilesspan in fts_documentsfilesspans:
                session.delete(fts_documentsfilesspan)
            # delete all FTS_DocumentsFilesDivs
            session.delete(fts_documentsfile)
        # delete all FTS_DocumentsFiles
        session.delete(fts_document)
        # commit the changes
        session.commit()

def pdf_to_documentsfilescontent(file):
    engine = create_engine(fts_config.dbftsurl)
    Session = sessionmaker(engine)
    with Session() as session:
        # convert the pdf to records
        convert_pdf_to_records(session, file)

def prepare_fts(appbuilder):
    engine = create_engine(fts_config.dbftsurl)
    Session = sessionmaker(engine)
    with Session() as session:
        # get the raw connection
        connection = session.connection()
        # enable the FTS
        enable_fts( db=connection.connection.dbapi_connection, 
                    content='ftsdocumentsfilesspans',
                    fts='ftsdocumentsfilescontent_fts',
                    columns=['div_id','text','font_family','font_size'], 
                    col_attrs={'div_id': 'UNINDEXED', 'font_family': 'UNINDEXED', 'font_size': 'UNINDEXED'})
