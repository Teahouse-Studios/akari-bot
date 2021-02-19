import datetime
import os
import sqlite3
import traceback

from graia.application import Group, Friend, Member

dbpath = os.path.abspath('./database/save.db')


def initialize():
    a = open(dbpath, 'w')
    a.close()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    c.execute('''CREATE TABLE group_permission
           (ID INT PRIMARY KEY     NOT NULL,
           ENABLE_MODULES  TEXT);''')
    c.execute('''CREATE TABLE self_permission
           (ID INT PRIMARY KEY     NOT NULL,
           DISABLE_MODULES  TEXT);''')
    c.execute('''CREATE TABLE black_list
           (ID INT PRIMARY KEY     NOT NULL);''')
    c.execute('''CREATE TABLE white_list
           (ID INT PRIMARY KEY     NOT NULL);''')
    c.execute('''CREATE TABLE warn
           (ID INT PRIMARY KEY     NOT NULL,
           WARN  TEXT);''')
    c.execute('''CREATE TABLE superuser
           (ID INT PRIMARY KEY     NOT NULL);''')
    c.execute('''CREATE TABLE time
           (ID INT PRIMARY KEY     NOT NULL,
           NAME  TEXT NOT NULL,
           TIME TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')
    c.close()


def connect_db(path):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    return c


def update_modules(do, id, modules_name, table='group_permission', value='ENABLE_MODULES'):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
    if do == 'add':
        if a:
            enabled_split = a[1].split('|')
            if modules_name in enabled_split:
                return '失败：模块已被启用：' + modules_name
            else:
                enabled_split.append(modules_name)
                c.execute(f"UPDATE {table} SET {value}='{'|'.join(enabled_split)}' WHERE ID='{id}'")
                conn.commit()
                return '成功：启用模块：' + modules_name
        else:
            c.execute(f"INSERT INTO {table} (ID, {value}) VALUES (?, ?)", (id, modules_name))
            conn.commit()
            return '成功：启用模块：' + modules_name
    elif do == 'del':
        if a:
            enabled_split = a[1].split('|')
            if modules_name in enabled_split:
                enabled_split.remove(modules_name)
                c.execute(f"UPDATE {table} SET {value}='{'|'.join(enabled_split)}' WHERE ID='{id}'")
                conn.commit()
                return '成功：禁用模块：' + modules_name
            else:
                return '失败：未启用过该模块：' + modules_name
        else:
            return '失败：未启用过该模块：' + modules_name


def update_modules_self(do, id, modules_name, table='self_permission', value='DISABLE_MODULES'):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM {table} WHERE ID={id}").fetchone()
    if do == 'del':
        if a:
            enabled_split = a[1].split('|')
            if modules_name in enabled_split:
                return '失败：模块已被禁用：' + modules_name
            else:
                enabled_split.append(modules_name)
                c.execute(f"UPDATE {table} SET {value}='{'|'.join(enabled_split)}' WHERE ID='{id}'")
                conn.commit()
                return '成功：禁用模块：' + modules_name
        else:
            c.execute(f"INSERT INTO {table} (ID, {value}) VALUES (?, ?)", (id, modules_name))
            conn.commit()
            return '成功：禁用模块：' + modules_name
    elif do == 'add':
        if a:
            enabled_split = a[1].split('|')
            if modules_name in enabled_split:
                enabled_split.remove(modules_name)
                c.execute(f"UPDATE {table} SET {value}='{'|'.join(enabled_split)}' WHERE ID='{id}'")
                conn.commit()
                return '成功：启用模块：' + modules_name
            else:
                return '失败：未禁用过该模块：' + modules_name
        else:
            return '失败：未禁用过该模块：' + modules_name


def check_enable_modules(kwargs, modules_name, table='group_permission'):
    if not os.path.exists(dbpath):
        initialize()
    if isinstance(kwargs, int):
        target = kwargs
    else:
        if Group in kwargs:
            table == 'group_permission'
            target = kwargs[Group].id
        if Friend in kwargs:
            table == 'self_permission'
            target = kwargs[Friend].id
    if table == 'group_permission':
        conn = sqlite3.connect(dbpath)
        c = conn.cursor()
        a = c.execute(f"SELECT * FROM {table} WHERE ID='{target}'").fetchone()
        if a:
            enabled_split = a[1].split('|')
            if modules_name in enabled_split:
                return True
            else:
                return False
        else:
            return False
    if table == 'self_permission':
        conn = sqlite3.connect(dbpath)
        c = conn.cursor()
        a = c.execute(f"SELECT * FROM {table} WHERE ID='{target}'").fetchone()
        if a:
            enabled_split = a[1].split('|')
            if modules_name in enabled_split:
                return False
            else:
                return True
        else:
            return True


def check_enable_modules_self(id, modules_name, table='self_permission'):
    if not os.path.exists(dbpath):
        initialize()
    if table == 'self_permission':
        conn = sqlite3.connect(dbpath)
        c = conn.cursor()
        a = c.execute(f"SELECT * FROM {table} WHERE ID='{id}'").fetchone()
        if a:
            enabled_split = a[1].split('|')
            if modules_name in enabled_split:
                return False
            else:
                return True
        else:
            return True


def check_enable_modules_all(table, modules_name):
    # 检查表中所有匹配的对象，返回一个list
    if not os.path.exists(dbpath):
        initialize()
    enable_target = []
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM {table}").fetchall()
    for x in a:
        enabled_split = x[1].split('|')
        if modules_name in enabled_split:
            enable_target.append(x[0])
    return enable_target


def add_black_list(id):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    c.execute(f"INSERT INTO black_list (ID) VALUES ('{id}')")
    conn.commit()
    c.close()


def add_white_list(id):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    c.execute(f"INSERT INTO white_list (ID) VALUES ('{id}')")
    conn.commit()
    c.close()


def check_black_list(id):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM black_list WHERE ID={id}").fetchone()
    if a:
        return True
    else:
        return False


def check_white_list(id):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM white_list WHERE ID={id}").fetchone()
    if a:
        return True
    else:
        return False


def check_superuser(kwargs: dict):
    if not os.path.exists(dbpath):
        initialize()
    if Group in kwargs:
        id = kwargs[Member].id
    if Friend in kwargs:
        id = kwargs[Friend].id
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM superuser WHERE ID={id}").fetchone()
    if a:
        return True
    else:
        return False


def add_superuser(id):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    try:
        c.execute(f"INSERT INTO superuser (ID) VALUES ('{id}')")
    except:
        traceback.print_exc()
    conn.commit()
    c.close()
    return '成功？我也不知道成没成，懒得写判断了（'


def del_superuser(id):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    try:
        c.execute(f"DELETE FROM superuser WHERE ID='{id}'")
    except:
        traceback.print_exc()
    conn.commit()
    c.close()
    return '成功？我也不知道成没成，懒得写判断了（'


def warn_someone(id):
    if not os.path.exists(dbpath):
        initialize()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM warn WHERE ID={id}").fetchone()
    if a:
        c.execute(f"UPDATE warn SET WARN='{int(a[1]) + 1}' WHERE ID='{id}'")
    else:
        c.execute(f"INSERT INTO warn (ID, WARN) VALUES (?, ?)", (id, 0,))
    conn.commit()
    if int(a[1]) > 5:
        add_black_list(id)


def write_time(kwargs, name):
    if not os.path.exists(dbpath):
        initialize()
    if Group in kwargs:
        id = kwargs[Member].id
    if Friend in kwargs:
        id = kwargs[Friend].id
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM time WHERE ID='{id}' and NAME='{name}'").fetchone()
    if a:
        print(a)
        c.execute(f"UPDATE time SET TIME=datetime('now') WHERE ID='{id}'")
        conn.commit()
    else:
        c.execute(f"INSERT INTO time (ID, NAME) VALUES (?, ?)", (id, name))
        conn.commit()


def check_time(kwargs, name, delay: int):
    if not os.path.exists(dbpath):
        initialize()
    if Group in kwargs:
        id = kwargs[Member].id
    if Friend in kwargs:
        id = kwargs[Friend].id
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    a = c.execute(f"SELECT * FROM time WHERE ID='{id}' and NAME='{name}'").fetchone()
    if a:
        print(a)
        print(datetime.datetime.strptime(a[2], "%Y-%m-%d %H:%M:%S").timestamp())
        print(datetime.datetime.now().timestamp())
        check = (datetime.datetime.strptime(a[2], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(
            hours=8)).timestamp() - datetime.datetime.now().timestamp()
        print(check)
        if check > - delay:
            return check
        else:
            return False
    else:
        return False
