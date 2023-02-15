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
import subprocess
import shutil
import fitz

logger = logging.getLogger(__name__)

__version__ = "0.0.1"
__author__ = "Gilbert Brault"
__email__ = "gbrault@seadev.org"
__license__ = "MIT"
__status__ = "Development"

# Functions ===========================================================================================================================

def flags_decomposer(flags):
    """Make font flags human readable."""
    l = {}
    if flags & 2 ** 0:
        l.update({"superscript": True})
    if flags & 2 ** 1:
        l.update({"italic": True})
    if flags & 2 ** 2:
        l.update({"serifed": True})
    else:
        l.update({"sans": True})
    if flags & 2 ** 3:
        l.update({"monospaced": True})
    else:
        l.update({"proportional": True})
    if flags & 2 ** 4:
        l.update({"bold": True})
    return l

def represent(table,paths):
    """Return a string representation of a table."""
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

class ftsDocumentsFiles(Model):
    """DocumentsFiles table"""
    __bind_key__ = fts_config.SCHEMA_FTS
    __tablename__ = 'ftsdocumentsfiles'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''DocumentsFiles table's record unique id''')
    file = Column(FileColumn, nullable=False,comment='''Document File name''')
    # start index timestamp
    start_index = Column(DateTime, nullable=False, default=datetime.datetime.now() ,comment='''Start index timestamp''')
    # end index timestamp
    end_index = Column(DateTime, nullable=False, default=datetime.datetime.now(), comment='''End index timestamp''')
    def __repr__(self):
        return f"{represent(self, ['file_name'])}"  
    def file_name(self):
        return get_file_original_name(str(self.file))
    def download(self):
        return Markup(
            '<a href="'
            + url_for("ftsDocumentsFilesView.download", filename=str(self.file))
            + f'">{self.file_name()}</a>'
        )
    def indexing_duration(self):
        return self.end_index - self.start_index

class ftsDocumentsFilesPages(Model):
    """DocumentsFilesPages table"""
    __bind_key__ = fts_config.SCHEMA_FTS
    __tablename__ = 'ftsdocumentsfilespages'
    __table_args__ = (
        ForeignKeyConstraint(
            ['document_id'],
            ['ftsdocumentsfiles.id']
            ),
    )    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''DocumentsFilesPages table's record unique id''')
    document_id = Column(Integer, nullable=False, comment='''document unique id (table ftsDocumentFiles)''')
    pnumber = Column(Integer, nullable=False, comment='''Page number''')
    width = Column(Float, nullable=False, comment='''width''')
    height = Column(Float, nullable=False, comment='''height''')
    documentfiles = relationship('ftsDocumentsFiles', backref='ftsdocumentsfilespages', foreign_keys=[document_id])
    def __repr__(self):
        return f"{get_file_original_name(self.documentfiles.file)} {self.pnumber}"
    def document_reference(self):
        return Markup(
            '<a href="'
            + url_for("ftsDocumentsFilesView.show", pk=self.document_id)
            + f'">{(str(self.documentfiles.file_name()))} - page {self.pnumber}</a>'
        )

class ftsDocumentsFilesTextBlocks(Model):
    """DocumentsFilesTextBlocks table"""
    __bind_key__ = fts_config.SCHEMA_FTS
    __tablename__ = 'ftsdocumentsfilestextblocks'
    __table_args__ = (
        ForeignKeyConstraint(
            ['page_id'],
            ['ftsdocumentsfilespages.id']
            ),
    )    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''DocumentsFilesTextBlocs table's record unique id''')
    page_id = Column(Integer, nullable=False, comment='''document page unique id (table ftsDocumentFilesPages)''')
    bnumber = Column(Integer, nullable=False, comment='''Block number''')
    btype = Column(Integer, nullable=False, default=0, comment='''Block type''')
    bbox0 = Column(Float, nullable=False, comment='''x left top''')
    bbox1 = Column(Float, nullable=False, comment='''y left top''')
    bbox2 = Column(Float, nullable=False, comment='''x right bottom''')
    bbox3 = Column(Float, nullable=False, comment='''y right bottom''')
    text = Column(Text, nullable=False, comment='''Block text''')
    size = Column(Float, nullable=False, comment='''Block size''')
    pages = relationship('ftsDocumentsFilesPages', backref='ftsdocumentsfilestextblocks', foreign_keys=[page_id])
    def file_name(self):
        return get_file_original_name(str(self.pages.documentfiles.file))
    def __repr__(self):
        return f"{self.file_name()} p:{self.pages.pnumber} b:{self.bnumber}"
    def page_reference(self):
        return Markup(
            '<a href="'
            + url_for("ftsDocumentFilesPagesView.show", pk=self.page_id)
            + f'">{self.pages.pnumber}</a>'
        )
    @renders('text')
    def highlight_text(self):
        text = self.text
        if text is None:
            return ''
        if hasattr(self,'_filters'):
            for i,filter in enumerate(self._filters.filters):
                if filter.column_name == 'text':
                    values_to_highlight = [ t for t in self._filters.values[i][0].split() if t not in ['AND','OR','NOT'] ]
                    for value in values_to_highlight:
                        value = value.strip('"').strip("'")
                        text = re.sub('(?i)'+re.escape(value), lambda k: '<mark>' + value + '</mark>', text)
            return Markup(text.replace('\n','<br>').replace('\r',''))
        else:
            return text
          

# Views ===========================================================================================================================================

class ftsDocumentsFilesView(ModelView):
    """DocumentsFilesView view"""
    datamodel = SQLAInterface(ftsDocumentsFiles)
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

class ftsDocumentFilesPagesView(ModelView):
    """DocumentsFilesPagesView view"""
    datamodel = SQLAInterface(ftsDocumentsFilesPages)
    list_columns = ['id', 'document_reference','width','height']
    label_columns = dict(
        id = 'Id',
        document_id = 'Document Id',
        pnumber = 'Page Number',
        width = 'width',
        height = 'height',
        document_reference = 'Document Reference'
        )
    show_columns = ['id', 'document_id','pnumber','width','height']
    edit_columns = ['document_id','pnumber','width','height']
    add_columns = [ 'document_id','pnumber','width','height']

class ftsDocumentFilesTextBlocksView(ModelView):
    """DocumentsFilesTextBlocksView view"""
    base_permissions = ['can_list']
    datamodel = SQLAInterface(ftsDocumentsFilesTextBlocks)
    list_columns = ['file_name','page_reference','highlight_text']
    label_columns = dict(
        id = 'Id',
        page_id = 'Page Id',
        bbox0 = 'Bbox0',
        bbox1 = 'Bbox1',
        bbox2 = 'Bbox2',
        bbox3 = 'Bbox3',
        text = 'Text',
        size = 'Size',
        page_reference = 'Page Reference',
        highlight_text = 'Text',
        file_name = 'File Name'
        )
    show_columns = ['id', 'page_id','bbox0','bbox1','bbox2','bbox3']
    edit_columns = ['page_id','bbox0','bbox1','bbox2','bbox3']
    add_columns = [ 'page_id','bbox0','bbox1','bbox2','bbox3']


# Menu ===========================================================================================================================================
def fts_menus(appbuilder):
    appbuilder.add_view(ftsDocumentsFilesView,"DocumentsFiles",icon="fa-file",category="Full_Text_Search")
    appbuilder.add_view(ftsDocumentFilesPagesView,"DocumentsFilesPages",icon="fa-files-o",category="Full_Text_Search")
    appbuilder.add_view(ftsDocumentFilesTextBlocksView,"DocumentsFilesTextBlocks",icon="fa-search",category="Documents")

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
                    self.threadpool.submit(self.pdf_to_documentsfilescontent, task['documentfiles'], task['username'])
                if task['action'] == 'delete':
                    self.threadpool.submit(self.pdf_delete, task['documentfiles'], task['username'])
            else:
                time.sleep(1)

    def index(self, documentfiles, username):
        # check if request already in tasklist
        for task in self.tasklist:
            if task['action'] == 'index' and task['documentfiles'] == documentfiles.file:
                self.appbuilder.send_alert(username,'Document already in tasklist for indexing',"alert-warning")
                return
        # check if the document is already indexed and flash a message and return if it is
        file = self.appbuilder.session.query(ftsDocumentsFiles).filter(ftsDocumentsFiles.file == documentfiles.file).all()
        if file is not None and len(file) > 0:
            if file[0].end_index == file[0].start_index:
                self.appbuilder.send_alert(username,'Document is indexing wait till end of indexing','alert-warning')
                return
            else:
                self.appbuilder.send_alert('Reindexing the Document','alert-info')
                # reindexing the document, so delete the document index
                self.tasklist.append({'action': 'delete', 'documentfiles': documentfiles.file, 'username': username})
                # add the document to the tasklist for indexing
                self.tasklist.append({'action': 'index', 'documentfiles': documentfiles.file, 'username': username})
                return
        # add the document to the tasklist for indexing
        self.tasklist.append({'action': 'index', 'documentfiles': documentfiles.file, 'username': username})
        self.appbuilder.send_alert(username, 'Document added to tasklist for indexing','alert-info')

    def delete(self, documentfiles, username):
        # check if request already in tasklist
        for task in self.tasklist:
            if task['action'] == 'delete' and task['documentfiles'] == documentfiles.file:
                self.appbuilder.send_alert(username,'Document already in tasklist for deleting','alert-warning')
                return
        doc = self.appbuilder.session.query(ftsDocumentsFiles).filter(ftsDocumentsFiles.file == documentfiles.file).all()
        if doc is not None and len(doc) > 0:
            self.tasklist.append({'action': 'delete', 'documentfiles': doc[0].id, 'username': username})

    def pdf_delete(self, id, username):
        engine = create_engine(fts_config.dbftsurl)
        Session = sessionmaker(engine)
        with Session() as session:
            # find the ftsDocuments Files with the id
            ftsdocument = session.query(ftsDocumentsFiles).filter(ftsDocumentsFiles.id == id).first()
            # delete the file and the html conversion
            try:
                # get the root directory
                rootpath = self.appbuilder.app.config['UPLOAD_FOLDER']
                # get the file path
                filepath = os.path.join(rootpath, ftsdocument.file.replace(".pdf", ""))
                # suppress the directory with shutil.rmtree
                shutil.rmtree(filepath)
            except Exception as e:
                logger.error("Error deleting file: {}".format(e))
            # for each ftsDocumentsFiles find all ftsDocumentsFilesPages
            ftsdocumentsfilespages = session.query(ftsDocumentsFilesPages).filter(ftsDocumentsFilesPages.document_id == id).all()
            # find all ftsDocumentsFilesBlocks with the page_id
            for ftsdocumentsfilepage in ftsdocumentsfilespages:
                ftsdocumentsfilestextblocs = session.query(ftsDocumentsFilesTextBlocks).filter(ftsDocumentsFilesTextBlocks.page_id == ftsdocumentsfilespages.id).all()
                # find all ftsDocumentsFilesLines with the textblock_id
                for ftsdocumentsfilestextbloc in ftsdocumentsfilestextblocs:
                    # delete all ftsDocumentsFilesTextBlocks
                    session.delete(ftsdocumentsfilestextbloc)
                # delete all ftsDocumentsFilesPages
                session.delete(ftsdocumentsfilepage)
            # delete all ftsDocumentsFiles
            session.delete(ftsdocument)
            # commit the changes
            session.commit()

    def pdf_to_documentsfilescontent(self, file, username):
        engine = create_engine(fts_config.dbftsurl)
        Session = sessionmaker(engine)
        with Session() as session:
            # convert the pdf to records
            try:
                # create the doumentfiles record
                documentsfile = ftsDocumentsFiles(file=file)
                session.add(documentsfile)
                session.commit()
                # get the root directory
                rootpath = self.appbuilder.app.config['UPLOAD_FOLDER']
                # get the file path
                filepath = os.path.join(rootpath, file)
                # read the pdf file with fitz
                doc = fitz.open(filepath)
                # navigate through the pages
                for page in doc:
                    # display the page number every 25 pages
                    if page.number % 25 == 0:
                        self.appbuilder.send_alert(username, f'Indexing page: {page.number}/{len(doc)}', 'alert-info')
                    # create the page record
                    documentsfilespage = ftsDocumentsFilesPages(   document_id=documentsfile.id,
                                                                    pnumber=page.number,
                                                                    width=page.rect.width,
                                                                    height=page.rect.height)
                    session.add(documentsfilespage)
                    session.commit()
                    # get the textblocks
                    textblocks = page.get_text("dict")["blocks"]
                    # navigate through the textblocks
                    for bno, textblock in enumerate(textblocks):
                        if textblock['type'] == 1:
                            continue
                        # create the textblock record
                        bbox0 = textblock["bbox"][0]
                        bbox1 = textblock["bbox"][1]
                        bbox2 = textblock["bbox"][2]
                        bbox3 = textblock["bbox"][3]
                        text = ""
                        size = 0
                        # get the lines
                        lines = textblock["lines"]
                        # navigate through the lines
                        for lno, line in enumerate(lines):
                            # get the spans
                            spans = line["spans"]
                            # navigate through the spans
                            for sno, span in enumerate(spans):
                                # get size and text
                                size = max(size,span["size"])
                                flags = span["flags"]
                                text += span["text"]
                # update the end time
                        documentsfilestextblock = ftsDocumentsFilesTextBlocks( page_id=documentsfilespage.id,
                                                                                bnumber = bno,
                                                                                bbox0=bbox0,
                                                                                bbox1=bbox1,
                                                                                bbox2=bbox2,
                                                                                bbox3=bbox3,
                                                                                text=text,
                                                                                size=size,)
                        session.add(documentsfilestextblock)
                        session.commit()
                documentsfile.end_index = datetime.datetime.now()
                session.commit()
                # send the end of indexing alert
                self.appbuilder.send_alert(username, f'The document has been indexed {file} in {documentsfile.end_index-documentsfile.start_index}', 'alert-success')
            except Exception as e:
                self.appbuilder.send_alert(username, 'Error during indexing the document: ' + str(e), 'alert-danger')

def prepare_fts(appbuilder):
    engine = create_engine(fts_config.dbftsurl)
    Session = sessionmaker(engine)
    with Session() as session:
        # get the raw connection
        connection = session.connection()
        # create view to search in the documents
        connection.execute('''CREATE VIEW IF NOT EXISTS ftsbyspans AS
                            SELECT
                                ROW_NUMBER() OVER() AS id,
                                ftsdocumentsfiles.id AS document_id,
                                ftsdocumentsfiles.file AS document_file,
                                ftsdocumentsfilespages.pnumber AS page_number,
                                ftsdocumentsfilespages.width AS page_width,
                                ftsdocumentsfilespages.height AS page_height,
                                ftsdocumentsfilestextblocks.bnumber AS textblock_number,
                                ftsdocumentsfilestextblocks.bbox0 AS textblock_bbox0,
                                ftsdocumentsfilestextblocks.bbox1 AS textblock_bbox1,
                                ftsdocumentsfilestextblocks.bbox2 AS textblock_bbox2,
                                ftsdocumentsfilestextblocks.bbox3 AS textblock_bbox3,
                                ftsdocumentsfileslines.lnumber AS line_number,
                                ftsdocumentsfileslines.bbox0 AS line_bbox0,
                                ftsdocumentsfileslines.bbox1 AS line_bbox1,
                                ftsdocumentsfileslines.bbox2 AS line_bbox2,
                                ftsdocumentsfileslines.bbox3 AS line_bbox3,
                                ftsdocumentsfileslines.wmode AS line_wmode,
                                ftsdocumentsfileslines.dir_0 AS line_dir_0,
                                ftsdocumentsfileslines.dir_1 AS line_dir_1,
                                ftsdocumentsfilesspans.snumber AS span_number,
                                ftsdocumentsfilesspans.text AS span_text,
                                ftsdocumentsfilesspans.bbox0 AS span_bbox0,
                                ftsdocumentsfilesspans.bbox1 AS span_bbox1,
                                ftsdocumentsfilesspans.bbox2 AS span_bbox2,
                                ftsdocumentsfilesspans.bbox3 AS span_bbox3,
                                ftsdocumentsfilesspans.color AS span_color,
                                ftsdocumentsfilesspans.font AS span_font,
                                ftsdocumentsfilesspans.size AS span_size,
                                ftsdocumentsfilesspans.flags AS span_flags,
                                ftsdocumentsfilesspans.origin_0 AS span_origin_0,
                                ftsdocumentsfilesspans.origin_1 AS span_origin_1
                            FROM
                                ftsdocumentsfiles
                            LEFT JOIN
                                ftsdocumentsfilespages ON ftsdocumentsfiles.id = ftsdocumentsfilespages.document_id
                            LEFT JOIN
                                ftsdocumentsfilestextblocks ON ftsdocumentsfilespages.id = ftsdocumentsfilestextblocks.page_id
                            LEFT JOIN
                                ftsdocumentsfileslines ON ftsdocumentsfilestextblocks.id = ftsdocumentsfileslines.block_id
                            LEFT JOIN
                                ftsdocumentsfilesspans ON ftsdocumentsfileslines.id = ftsdocumentsfilesspans.line_id
                            ORDER BY
                                ftsdocumentsfiles.id,
                                ftsdocumentsfilespages.pnumber,
                                ftsdocumentsfilestextblocks.bnumber,
                                ftsdocumentsfileslines.lnumber,
                                ftsdocumentsfilesspans.snumber''')
        # create view grouping spans by textblock
        connection.execute('''CREATE VIEW IF NOT EXISTS ftsbyblocks AS
                            SELECT
                                ROW_NUMBER() OVER (ORDER BY ftsdocumentsfiles.id, ftsdocumentsfilespages.pnumber, ftsdocumentsfilestextblocks.bnumber) AS id,
                                ftsdocumentsfiles.id AS document_id,
                                ftsdocumentsfiles.file AS document_file,
                                ftsdocumentsfilespages.pnumber AS page_number,
                                ftsdocumentsfilespages.width AS page_width,
                                ftsdocumentsfilespages.height AS page_height,
                                ftsdocumentsfilestextblocks.bnumber AS textblock_number,
                                ftsdocumentsfilestextblocks.bbox0 AS textblock_bbox0,
                                ftsdocumentsfilestextblocks.bbox1 AS textblock_bbox1,
                                ftsdocumentsfilestextblocks.bbox2 AS textblock_bbox2,
                                ftsdocumentsfilestextblocks.bbox3 AS textblock_bbox3,
                                GROUP_CONCAT(ftsdocumentsfilesspans.text, ' ') AS textblock_text
                            FROM
                                ftsdocumentsfiles
                            LEFT JOIN
                                ftsdocumentsfilespages ON ftsdocumentsfiles.id = ftsdocumentsfilespages.document_id
                            LEFT JOIN
                                ftsdocumentsfilestextblocks ON ftsdocumentsfilespages.id = ftsdocumentsfilestextblocks.page_id
                            LEFT JOIN
                                ftsdocumentsfileslines ON ftsdocumentsfilestextblocks.id = ftsdocumentsfileslines.block_id
                            LEFT JOIN
                                ftsdocumentsfilesspans ON ftsdocumentsfileslines.id = ftsdocumentsfilesspans.line_id
                            GROUP BY
                                ftsdocumentsfiles.id,
                                ftsdocumentsfilespages.pnumber,
                                ftsdocumentsfilestextblocks.bnumber
                            ORDER BY
                                ftsdocumentsfiles.id,
                                ftsdocumentsfilespages.pnumber,
                                ftsdocumentsfilestextblocks.bbox1,
                                ftsdocumentsfilestextblocks.bbox0''')