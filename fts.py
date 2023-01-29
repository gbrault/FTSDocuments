"""Full Text Shearch for Flask App Builder
"""
import fitz
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

RATIO = 50

def enable_fts(db: Connection, table: str, columns: List[str], col_attrs: dict):
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
    sql_script_1 = '''
        CREATE VIRTUAL TABLE IF NOT EXISTS `{table}_fts` USING fts5
        (
            {column_list_wattrs},
            content=`{table}`
        )'''.format(
        table=table,
        column_list_wattrs=column_list_wattrs
    )
    db.executescript(sql_script_1)

    cursor = db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(tables)

    sql_script_2 ='''
        CREATE TRIGGER IF NOT EXISTS `{table}_fts_insert` AFTER INSERT ON `{table}`
        BEGIN
            INSERT INTO `{table}_fts` (rowid, {column_list}) VALUES (new.rowid, {new_columns});
        END;
        CREATE TRIGGER IF NOT EXISTS `{table}_fts_delete` AFTER DELETE ON `{table}`
        BEGIN
            INSERT INTO `{table}_fts` (`{table}_fts`, rowid, {column_list}) VALUES ('delete', old.rowid, {old_columns});
        END;
        CREATE TRIGGER IF NOT EXISTS `{table}_fts_update` AFTER UPDATE ON `{table}`
        BEGIN
            INSERT INTO `{table}_fts` (`{table}_fts`, rowid, {column_list}) VALUES ('delete', old.rowid, {old_columns});
            INSERT INTO `{table}_fts` (rowid, {column_list}) VALUES (new.rowid, {new_columns});
        END;
    '''.format(
        table=table,
        column_list=column_list,
        new_columns=','.join(f'new.`{c}`' for c in columns),
        old_columns=','.join(f'old.`{c}`' for c in columns),
    )

    db.executescript(sql_script_2)

    # TODO: add support for other databases
    sql_script_3='''SELECT `ftsdocumentsfilescontent_fts`.document_id,
    `ftsdocumentfiles`.`file`,
    `ftsdocumentsfilescontent`.`page`,
    `ftsdocumentsfilescontent_fts`.`text`,
    `ftsdocumentsfilescontent_fts`.`font`,
    `ftsdocumentsfilescontent_fts`.`size`
    FROM `ftsdocumentsfilescontent_fts` JOIN `ftsdocumentsfilescontent` ON `ftsdocumentsfilescontent`.rowid = `ftsdocumentsfilescontent_fts`.rowid
    JOIN `ftsdocumentfiles` ON `ftsdocumentfiles`.id = `ftsdocumentsfilescontent`.document_id
    '''.format(table=table)
    db.executescript(sql_script_3)

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

def vertical_overlap(box1,box2):
    """
    This function takes in two boxes in the form of dicts {"xlt":x1, "ylt":y1, "xrb":x2, "yrb":y2, "text":t} where (x1, y1) is the top-left corner, (x2, y2) is the bottom-right corner and t is the text.
    It returns True if the boxes are overlapping vertically, False otherwise
    simplify (box1["ylt"] <= box2["ylt"] and box1["yrb"] >= box2["ylt"]) or (box1["ylt"] <= box2["yrb"] and box1["yrb"] >= box2["yrb"]) yield to the following: box1["ylt"] <= box2["yrb"] and box1["yrb"] >= box2["ylt"]
    """
    if box1["ylt"] <= box2["yrb"] and box1["yrb"] >= box2["ylt"]:
        return True
    return False

def horizontal_overlap(box1,box2):
    """
    This function takes in two boxes in the form of dicts {"xlt":x1, "ylt":y1, "xrb":x2, "yrb":y2, "text":t} where (x1, y1) is the top-left corner, (x2, y2) is the bottom-right corner and t is the text.
    It returns True if the boxes are overlapping horizontally, False otherwise
    simplify (box1["xlt"] <= box2["xlt"] and box1["xrb"] >= box2["xlt"]) or (box1["xlt"] <= box2["xrb"] and box1["xrb"] >= box2["xrb"]) yield to the following: box1["xlt"] <= box2["xrb"] and box1["xrb"] >= box2["xlt"]
    """
    if box1["xlt"] <= box2["xrb"] and box1["xrb"] >= box2["xlt"]:
        return True
    return False

def englobe(current_box,box2):
    """Enlrge the current box to englobe the box2"""
    current_box["xlt"] = min(current_box["xlt"], box2["xlt"])
    current_box["xrb"] = max(current_box["xrb"], box2["xrb"])
    current_box["ylt"] = min(current_box["ylt"], box2["ylt"])
    current_box["yrb"] = max(current_box["yrb"], box2["yrb"])

def harmonize_font_size(current_box,box2):
    """Harmonize the font size of the current box and the box2"""
    current_box["size"] = min(current_box["size"], box2["size"])
    if len(current_box["text"]) < len(box2["text"]):
        current_box["font"] = box2["font"]

def find_largest_connex_rectangles(boxes,ratio):
    """
    This function takes in a list of boxes in the form of dicts {"xlt":x1, "ylt":y1, "xrb":x2, "yrb":y2, "text":t, "page":p, "font":f, "size":s} 
    where (x1, y1) is the top-left corner, (x2, y2) is the bottom-right corner and t is the text and p is the page number.
    f is the font name and s is the font size.
    A parameter epsilon is used to determine proximity of boxes. It is calculated as a ratio% of the height of the box.
    The function returns a list of "largest rectangles". 
    Each largest rectangle is a list of boxes that are connexe and with the same font and size.
    The boxes are sorted from top to bottom, left to right
    """
    # Find the list of largest rectangles
    largest_rectangles = []
    for i, box1 in enumerate(boxes):
        epsilon = ((box1["yrb"] - box1["ylt"])*ratio)/100 # ratio% of the height of the box
        if 'visited' not in box1:
            box1.update({"visited": True})
            group = [box1]
            current_box = box1
            for j, box2 in enumerate(boxes):
                if not 'visited' in box2:
                    # Check if the boxes are adjacent from the horizontal perspective
                    if ( (box2["xlt"]-current_box["xrb"]) < epsilon and # current_box is on the left of box2 all left boxes of box2 are already visited this expression is > 0
                            (vertical_overlap(box2,current_box)) and # current_box and box2 are overlapping vertically
                            # (box2["font"] == current_box["font"]) and # current_box and box2 have the same font
                            ((box2["size"] == current_box["size"]) or# current_box and box2 have the same font size
                            # the number of characters in last box is less than 3
                            (len(group[-1]["text"]) < 3)
                            )
                        ):
                        group.append(box2)
                        box2.update({"visited": True})
                        englobe(current_box,box2)
                        # makes sure the size and font of the group are the same
                        harmonize_font_size(current_box,box2)
                    # Check if the boxes are adjacent from the vertical perspective
                    elif abs(box2["ylt"] - (current_box["yrb"]) < epsilon and # box2 is on the top of current_box
                            (horizontal_overlap(box2,current_box))  and # current_box and box2 are overlapping horizontally
                            # (box2["font"] == current_box["font"]) and # current_box and box2 have the same font
                            ((box2["size"] == current_box["size"]) or # current_box and box2 have the same font size
                            # the number of characters in last box is less than 3
                            (len(group[-1]["text"]) < 3)
                            )
                        ):
                        group.append(box2)
                        box2.update({"visited": True})
                        englobe(current_box,box2)
                        # makes sure the size and font of the group are the same
                        harmonize_font_size(current_box,box2)
            rec = [current_box["xlt"], current_box["ylt"], current_box["xrb"], current_box["yrb"]]
            largest_rectangles.append({"page": boxes[0]["page"], "rec": rec,"group":sorted(group, key=lambda x: (x["ylt"],x["xlt"]))})
    return largest_rectangles

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

# get bocks of text from pdf file on disk using fitz
def read_doc(doc):
    unreadable_text_len = 0
    text_len = 0
    all_rectangles = []
    for page in doc:
        blocks = page.get_text("dict", flags=11)["blocks"]
        # select blocks in the table
        crop_blocks = []
        for b in blocks:
            for l in b["lines"]:
                for s in l["spans"]:
                    if s["text"].strip() != "":
                        block = {}
                        block.update({"font": s["font"]})     # font name
                        block.update({"style": flags_decomposer(s["flags"])})  # readable font flags
                        block.update({"size": s["size"]})     # font size
                        block.update({"color": s["color"]})   # font color
                        block.update({"text": s["text"]})     # text
                        block.update({"xlt": s["bbox"][0] })  # x left top
                        block.update({"ylt": s["bbox"][1] })  # y left top
                        block.update({"xrb": s["bbox"][2] })  # x right bottom
                        block.update({"yrb": s["bbox"][3] })  # y right bottom
                        block.update({"page": page.number })  # page number of the block
                        if l["dir"] == (0, -1):
                            block.update({"dir": 1})     # text direction 0=horizontal, 1=vertical                 
                        text_len += len(s["text"])
                        crop_blocks.append(block)
        sorted_crop_blocks = sorted(crop_blocks, key=lambda item: (item['ylt'],item['xlt']) )
        all_rectangles.extend(find_largest_connex_rectangles(sorted_crop_blocks,RATIO))
    return all_rectangles

__version__ = "0.0.1"
__author__ = "Gilbert Brault"
__email__ = "gbrault@seadev.org"
__license__ = "MIT"
__status__ = "Development"

# Models ===========================================================================================================================

class FTS_DocumentFiles(Model):
    __bind_key__ = fts_config.SCHEMA_FTS
    __tablename__ = 'ftsdocumentfiles'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''DocumentFiles table's record unique id''')
    file = Column(FileColumn, nullable=False,comment='''Document File''')
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

class FTS_DocumentsFilesContent(Model):
    __bind_key__ = fts_config.SCHEMA_FTS
    __tablename__ = 'ftsdocumentsfilescontent'
    __table_args__ = (
        ForeignKeyConstraint(
            ['document_id'],
            ['ftsdocumentfiles.id']
            ),
    )    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, comment='''DocumentsFilesContent table's record unique id''')
    document_id = Column(Integer, nullable=False, comment='''DB unique record identifier of the document''')
    font = Column(String(255), nullable=False, comment='''Font name''')
    size = Column(Float, nullable=False, comment='''Font size''')
    text = Column(Text, nullable=False, comment='''Text''')
    xlt = Column(Float, nullable=False, comment='''x left top''')
    ylt = Column(Float, nullable=False, comment='''y left top''')
    xrb = Column(Float, nullable=False, comment='''x right bottom''')
    yrb = Column(Float, nullable=False, comment='''y right bottom''')
    page = Column(Integer, nullable=False, comment='''Page number of the block''')
    documentfiles = relationship('FTS_DocumentFiles', backref='ftsdocumentsfilescontent', foreign_keys=[document_id])
            

# Views ===========================================================================================================================================

class FTS_DocumentFilesView(ModelView):
    datamodel = SQLAInterface(FTS_DocumentFiles)
    list_columns = ['id', 'download']
    label_columns = dict(
        id = 'Id',
        file = 'File'
        )
    show_columns = ['id', 'file']
    edit_columns = ['file']
    add_columns = [ 'file']

class FTS_DocumentsFilesContentView(ModelView):
    datamodel = SQLAInterface(FTS_DocumentsFilesContent)
    label_columns = dict(
        id = 'Id',
        document_id = 'Document Id',
        font = 'Font',
        size = 'Size',
        text = 'Text',
        xlt = 'Xlt',
        ylt = 'Ylt',
        xrb = 'Xrb',
        yrb = 'Yrb',
        page = 'Page'
        )
    description_columns = dict(
        id = 'DocumentFilesContent table\'s record unique id',
        document_id = 'DB unique record identifier of the document',
        font = 'Font name',
        size = 'Font size',
        text = 'Text',
        xlt = 'x left top',
        ylt = 'y left top',
        xrb = 'x right bottom',
        yrb = 'y right bottom',
        page = 'Page number of the block'
        )
    list_columns = ['size', 'page', 'text']
    show_columns = ['id', 'document_id', 'font', 'size',  'text', 'xlt', 'ylt', 'xrb', 'yrb', 'page']
    add_columns = [ 'document_id', 'font', 'size', 'text', 'xlt', 'ylt', 'xrb', 'yrb', 'page']
    edit_columns = [ 'document_id', 'font', 'size', 'text', 'xlt', 'ylt', 'xrb', 'yrb', 'page']

# Menu ===========================================================================================================================================
def fts_menus(appbuilder):
    appbuilder.add_view(FTS_DocumentFilesView,"DocumentsFiles",icon="fa-file",category="Full_Text_Search")
    appbuilder.add_view(FTS_DocumentsFilesContentView,"DocumentsFilesContent",icon="fa-search",category="Full_Text_Search")
    appbuilder.add_view(FTS_LEAN_VIEWView,"Documents Full Text Search",icon="fa-binoculars",category="Documents")

# FTSSearch ===========================================================================================================================================

def pdf_delete(documentfiles):
    engine = create_engine(fts_config.dbftsurl)
    Session = sessionmaker(engine)
    with Session() as session:
        # delete all the records of FTS_DocumentsFilesContent
        session.query(FTS_DocumentsFilesContent).filter(FTS_DocumentsFilesContent.document_id == documentfiles.id).delete()
        session.commit()
        # delete all the records of FTS_DocumentsFiles
        session.query(FTS_DocumentFiles).filter(FTS_DocumentFiles.id == documentfiles.id).delete()
        session.commit()

def pdf_to_documentsfilescontent(documentfiles):
    engine = create_engine(fts_config.dbftsurl)
    Session = sessionmaker(engine)
    with Session() as session:
        fts_documentFiles = FTS_DocumentFiles(
            file = documentfiles.file
        )
        session.add(fts_documentFiles)
        session.commit()
        doc = fitz.open(os.path.join(fts_config.UPLOAD_FOLDER,documentfiles.file))
        # find the rectangles of the doc
        # rectangles is a list of dictionaries with the following keys
        # page,rec,group
        # page is the page number
        # rec is a rectangle (xlt,ylt,xrb,yrb)
        # group is a list of boxes
        # each box is a dictionary with the following keys
        # font, size, text, xlt, ylt, xrb, yrb, page (style and visited are not used)
        rectangles = read_doc(doc)
        # all groups items have the same font, size
        # for each group
        #   remember the font, size and page
        #   merge the text of the subgroup
        #   get the xlt,ylt,xrb,yrb of the subgroup
        #   insert the result into the FTS_DocumentsFilesContent table
        for rectangle in rectangles:
            page = rectangle["page"]
            group = rectangle["group"]
            # get the font, size and page of the first box of the group
            font = group[0]["font"]
            size = group[0]["size"]
            page = group[0]["page"]
            text = ""
            xlt = 0
            ylt = 0
            xrb = 0
            yrb = 0
            for box in group:
                # if the box is under the previous one, add a new line character else add a space
                if group.index(box) > 0 and box["ylt"] > group[group.index(box)-1]["yrb"]:
                    text += "\n"
                else:
                    text += " "
                text += box["text"]+ " "
                if xlt == 0:
                    xlt = box["xlt"]
                if ylt == 0:
                    ylt = box["ylt"]
                if xrb == 0:
                    xrb = box["xrb"]
                if yrb == 0:
                    yrb = box["yrb"]
                if box["xlt"] < xlt:
                    xlt = box["xlt"]
                if box["ylt"] < ylt:
                    ylt = box["ylt"]
                if box["xrb"] > xrb:
                    xrb = box["xrb"]
                if box["yrb"] > yrb:
                    yrb = box["yrb"]
            fts_documentsfilescontent = FTS_DocumentsFilesContent(
                document_id = fts_documentFiles.id,
                font = font,
                size = size,
                text = text,
                xlt = xlt,
                ylt = ylt,
                xrb = xrb,
                yrb = yrb,
                page = page
            )
            session.add(fts_documentsfilescontent)
            session.commit()

def prepare_fts(appbuilder):
    engine = create_engine(fts_config.dbftsurl)
    Session = sessionmaker(engine)
    with Session() as session:
        # get the raw connection
        connection = session.connection()
        # enable the FTS
        enable_fts(connection.connection.dbapi_connection, 'ftsdocumentsfilescontent', ['document_id', 'page','text','font','size'], {'document_id': 'UNINDEXED', 'page': 'UNINDEXED', 'font': 'UNINDEXED', 'size': 'UNINDEXED'})
