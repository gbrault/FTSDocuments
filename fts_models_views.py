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
from flask import g, redirect, url_for, Markup, current_app
import sqlite3
from sqlite3 import Connection
from typing import List
from flask_appbuilder.models.decorators import renders
import re
# Models ===========================================================================================================================

class FTS_LEAN_VIEW(Model):
    __bind_key__ = fts_config.SCHEMA_FTS
    __table__ = Table('ftsdocumentsfilescontent_fts', Model.metadata,
        Column('rowid', Integer, primary_key=True, comment='''View unique id'''),
        Column('div_id', Integer, comment='''View document unique id'''),
        Column('text', Text, comment='''View document text'''),
        Column('font_family', String(255), nullable=False, comment='''View span font'''),
        Column('font_size', Integer, nullable=False, comment='''View span font size'''),
    )
    @renders('text')
    def highlight_text(self):
        # get the texts from the div_id spans
        session = current_app.appbuilder.get_session
        from fts import FTS_DocumentsFilesDivs, FTS_DocumentsFilesSpans
        div = session.query(FTS_DocumentsFilesDivs).filter_by(id=self.div_id).first()
        spans = session.query(FTS_DocumentsFilesSpans).filter_by(div_id=div.id).all()
        text = ''
        for span in spans:
            text += span.text + "<br>"
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
    @renders('document_id')
    def download_link(self):
        # need to get the document name from the document table
        # get the session from the appbuilder
        from fts import FTS_DocumentFiles, FTS_DocumentsFilesDivs
        session = current_app.appbuilder.get_session
        # get the document_id from the div_id
        doc_div = session.query(FTS_DocumentsFilesDivs).filter(FTS_DocumentsFilesDivs.id == self.div_id).first()
        document_id = doc_div.document_id
        # get  the document name from the document table using the document file
        file = session.query(FTS_DocumentFiles.file).filter(FTS_DocumentFiles.id == document_id).first()[0]
        as_attachment = 0
        return Markup(f'''<a href="{url_for('FTS_DocumentFilesView.download', filename=file, as_attachment=as_attachment)}" target="_blank">[{document_id}] {get_file_original_name(file).replace(".pdf","").strip("_")}</a>''')
    @renders('page')
    def page(self):
        from fts import FTS_DocumentsFilesDivs
        session = current_app.appbuilder.get_session
        doc_div = session.query(FTS_DocumentsFilesDivs).filter(FTS_DocumentsFilesDivs.id == self.div_id).first()
        return doc_div.page

# Views ===========================================================================================================================================

class FTS_LEAN_VIEWView(ModelView):
    datamodel = SQLAInterface(FTS_LEAN_VIEW)
    base_permissions = ['can_list']
    list_columns = ['download_link','page', 'highlight_text'] # ['rowid', 'download_link', 'page', 'highlight_text', 'font', 'size']
    label_columns = dict(
        rowid = 'Id',
        document_id = 'Document Id',
        page = 'Page',
        highlight_text = 'Text',
        font_familly = 'Font',
        font_size = 'Size'
        )