import base64
import os
import re
import sqlite3
import traceback

dbpath = os.path.abspath('./modules/wiki/save.db')


class WD:
    def __init__(self):
        if not os.path.exists(dbpath):
            self.initialize()

        self.conn = sqlite3.connect(dbpath)
        self.c = self.conn.cursor()

    def initialize(self):
        a = open(dbpath, 'w')
        a.close()
        self.conn = sqlite3.connect(dbpath)
        self.c = self.conn.cursor()
        self.c.execute('''CREATE TABLE start_wiki_link_group
               (ID INT PRIMARY KEY     NOT NULL,
               LINK  TEXT);''')
        self.c.execute('''CREATE TABLE custom_interwiki_group
               (ID INT PRIMARY KEY     NOT NULL,
               INTERWIKIS  TEXT);''')
        self.c.execute('''CREATE TABLE start_wiki_link_self
               (ID INT PRIMARY KEY     NOT NULL,
               LINK  TEXT);''')
        self.c.execute('''CREATE TABLE custom_interwiki_self
               (ID INT PRIMARY KEY     NOT NULL,
               INTERWIKIS  TEXT);''')
        self.c.execute('''CREATE TABLE wiki_info
               (LINK TEXT PRIMARY KEY     NOT NULL,
               SITEINFO  TEXT,
               TS  TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')
        self.c.execute('''CREATE TABLE request_headers_group
               (ID TEXT PRIMARY KEY     NOT NULL,
               HEADERS  TEXT);''')
        self.c.execute('''CREATE TABLE request_headers_self
               (ID TEXT PRIMARY KEY     NOT NULL,
               HEADERS  TEXT);''')
        self.c.close()

    def add_start_wiki(self, table, id, value):
        a = self.c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
        if a:
            self.c.execute(f"UPDATE {table} SET LINK='{value}' WHERE ID='{id}'")
            self.conn.commit()
            return '成功设置起始Wiki：'
        else:
            self.c.execute(f"INSERT INTO {table} (ID, Link) VALUES (?, ?)", (id, value))
            self.conn.commit()
            return '成功设置起始Wiki：'

    def get_start_wiki(self, table, id):
        a = self.c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
        if a:
            return a[1]
        else:
            return False

    def config_custom_interwiki(self, do, table, id, iw, link=None):
        a = self.c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
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
                    self.c.execute(
                        f"UPDATE {table} SET INTERWIKIS='{'|'.join(split_iws)}' WHERE ID='{id}'")
                    self.conn.commit()
                    return '成功：更新自定义Interwiki：'
                else:
                    split_iws.append(f'{iw}>{link}')
                    self.c.execute(
                        f"UPDATE {table} SET INTERWIKIS='{'|'.join(split_iws)}' WHERE ID='{id}'")
                    self.conn.commit()
                    return '成功：添加自定义Interwiki：'
            else:
                self.c.execute(f"INSERT INTO {table} (ID, INTERWIKIS) VALUES (?, ?)", (id, f'{iw}>{link}'))
                self.conn.commit()
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
                    self.c.execute(
                        f"UPDATE {table} SET INTERWIKIS='{'|'.join(split_iws)}' WHERE ID='{id}'")
                    self.conn.commit()
                    return '成功：删除自定义Interwiki：'
                else:
                    return '失败：添加过此Interwiki：'
            else:
                return '失败：未添加过任何Interwiki。'

    def get_custom_interwiki(self, table, id, iw):
        a = self.c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
        if a:
            interwikis = a[1].split('|')
            for iws in interwikis:
                if iws.find(iw + '>') != -1:
                    iws = iws.split('>')
                    return iws[1]
        else:
            return False

    def get_custom_interwiki_list(self, table, id):
        a = self.c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
        if a:
            interwikis = a[1].split('|')
            return '\n'.join(interwikis)
        else:
            return False

    def config_headers(self, do, table, id, header=None):
        try:
            a = self.c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
            if do == 'set':
                header = base64.encodebytes(header.encode('utf-8'))
                if a:
                    self.c.execute(f"UPDATE {table} SET HEADERS='{header}' WHERE ID='{id}'")
                else:
                    self.c.execute(f"INSERT INTO {table} (ID, HEADERS) VALUES (?, ?)", (id, header))
                self.conn.commit()
                return '成功更新请求所使用的Headers。'
            elif do == 'reset':
                if a:
                    self.c.execute(f"DELETE FROM {table} WHERE ID='{id}'")
                    return '成功重置请求所使用的Headers。'
                else:
                    return '当前未自定义请求所使用的Headers。'
            elif do == 'get':
                headers = {}
                if a:
                    headerd = str(base64.decodebytes(a[1]).decode('utf-8'))
                    headersp = headerd.split('\n')
                    for x in headersp:
                        x = x.split(':')
                        headers[x[0]] = re.sub(r'^ ', '', x[1])
                else:
                    headers['accept-language'] = 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'
                print(header)
                return headers
            elif do == 'show':
                if a:
                    header = str(base64.decodebytes(a[1]).decode('utf-8'))
                else:
                    header = '（默认）accept-language: zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'
                return header
        except Exception as e:
            traceback.print_exc()
            return '发生错误' + str(e)

    def update_wikiinfo(self, apilink, siteinfo):
        a = self.c.execute(f"SELECT * FROM wiki_info WHERE LINK='{apilink}'").fetchone()
        if a:
            self.c.execute("UPDATE wiki_info SET SITEINFO=? WHERE LINK=?", (siteinfo, apilink))
        else:
            self.c.execute(f"INSERT INTO wiki_info (LINK, SITEINFO) VALUES (?, ?)", (apilink, siteinfo))
        self.conn.commit()

    def get_wikiinfo(self, apilink):
        a = self.c.execute(f"SELECT * FROM wiki_info WHERE LINK='{apilink}'").fetchone()
        if a:
            return a[1:]
        else:
            return False


WikiDB = WD()
