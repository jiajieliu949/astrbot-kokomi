import os
import sqlite3
from ..path import plugin_path

def create_new_db():
    db_path = os.path.join(plugin_path, 'db', 'user_pic.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    table_create_query = f'''
    CREATE TABLE pic (
        id str PRIMARY KEY,
        pic int
    );
    '''
    cursor.execute(table_create_query)
    conn.commit()
    cursor.close()
    conn.close()

def get_pic(
    id: str
):
    db_path = os.path.join(plugin_path, 'db', 'user_pic.db')
    if os.path.exists(db_path) is False:
        create_new_db()
    conn = sqlite3.connect(database=db_path)
    cursor = conn.cursor()
    query = f"SELECT * FROM pic WHERE id = '{id}'"
    cursor.execute(query)
    data = cursor.fetchone()
    if data is None:
        pic_num = 1
    else:
        pic_num = data[1]
    cursor.close()
    conn.close()
    return pic_num

def change_pic(
    id: str,
    pic_num: str
):
    db_path = os.path.join(plugin_path, 'db', 'user_pic.db')
    if os.path.exists(db_path) is False:
        create_new_db()
    conn = sqlite3.connect(database=db_path)
    cursor = conn.cursor()
    query = f"SELECT * FROM pic WHERE id = '{id}'"
    cursor.execute(query)
    data = cursor.fetchone()
    if data is None:
        if pic_num == 1:
            pass
        else:
            insert_data = (
                id,
                pic_num,
            )
            insert_query = f'''
            INSERT INTO pic (
                id,
                pic
            ) VALUES (
                ?, ?
            )'''
            cursor.execute(insert_query, insert_data)
            conn.commit()
    else:
        if pic_num == 1:
            delete_data = (
                id,
            )
            delete_sql = '''
            DELETE FROM pic
            WHERE 
                id = ?
            '''
            cursor.execute(delete_sql, delete_data)
            conn.commit()
        else:
            replace_data = (
                id,
                pic_num,
            )
            replace_query = f'''
            REPLACE INTO pic (
                id,
                pic
            ) VALUES (
                ?, ?
            )'''
            cursor.execute(replace_query, replace_data)
            conn.commit()
    cursor.close()
    conn.close()
