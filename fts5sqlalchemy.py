from sqlite3 import Connection
from typing import List

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