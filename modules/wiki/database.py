import os
import sqlite3

dbpath = os.path.abspath('./modules/wiki/save.db')


def initialize():
    a = open(dbpath, 'w')
    a.close()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    c.execute('''CREATE TABLE start_wiki_link_group
           (ID INT PRIMARY KEY     NOT NULL,
           LINK  TEXT);''')
    c.execute('''CREATE TABLE custom_interwiki_group
           (ID INT PRIMARY KEY     NOT NULL,
           INTERWIKIS  TEXT);''')
    c.execute('''CREATE TABLE start_wiki_link_self
           (ID INT PRIMARY KEY     NOT NULL,
           LINK  TEXT);''')
    c.execute('''CREATE TABLE custom_interwiki_self
           (ID INT PRIMARY KEY     NOT NULL,
           INTERWIKIS  TEXT);''')
    c.close()


def add_start_wiki(table, id, value):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
    if a:
        c.execute(f"UPDATE {table} SET LINK='{value}' WHERE ID='{id}'")
        conn.commit()
        return '成功设置起始Wiki：'
    else:
        c.execute(f"INSERT INTO {table} (ID, Link) VALUES (?, ?)", (id, value))
        conn.commit()
        return '成功设置起始Wiki：'


def get_start_wiki(table, id):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
    if a:
        return a[1]
    else:
        return False


def config_custom_interwiki(do, table, id, iw, link=None):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
    if do == 'add':
        if a:
            split_iws = a[1].split('|')
            iwlist = []
            for iws in split_iws:
                split_iw = iws.split('>')
                iwlist.append(split_iw[0])
            if iw in iwlist:
                for iws in split_iws:
                    if iws.find(iw + '>') != -1:
                        split_iws.remove(iws)
                split_iws.append(f'{iw}>{link}')
                c.execute(
                    f"UPDATE {table} SET INTERWIKIS='{'|'.join(split_iws)}' WHERE ID='{id}'")
                conn.commit()
                return '成功：更新自定义Interwiki：'
            else:
                split_iws.append(f'{iw}>{link}')
                c.execute(
                    f"UPDATE {table} SET INTERWIKIS='{'|'.join(split_iws)}' WHERE ID='{id}'")
                conn.commit()
                return '成功：添加自定义Interwiki：'
        else:
            c.execute(f"INSERT INTO {table} (ID, INTERWIKIS) VALUES (?, ?)", (id, f'{iw}>{link}'))
            conn.commit()
            return '成功：添加自定义Interwiki：'
    elif do == 'del':
        if a:
            split_iws = a[1].split('|')
            iwlist = []
            for iws in split_iws:
                split_iw = iws.split('>')
                iwlist.append(split_iw[0])
            if iw in iwlist:
                for iws in split_iws:
                    if iws.find(iw + '>') != -1:
                        split_iws.remove(iws)
                c.execute(
                    f"UPDATE {table} SET INTERWIKIS='{'|'.join(split_iws)}' WHERE ID='{id}'")
                conn.commit()
                return '成功：删除自定义Interwiki：'
            else:
                return '失败：添加过此Interwiki：'
        else:
            return '失败：未添加过任何Interwiki。'


def get_custom_interwiki(table, id, iw):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
    if a:
        interwikis = a[1].split('|')
        for iws in interwikis:
            if iws.find(iw + '>') != -1:
                iws = iws.split('>')
                return iws[1]
    else:
        return False


def get_custom_interwiki_list(table, id):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
    if a:
        interwikis = a[1].split('|')
        return '\n'.join(interwikis)
    else:
        return False
