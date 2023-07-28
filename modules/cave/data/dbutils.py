import ujson as json
from database import session, auto_rollback_error
from .orm import Caves
from tenacity import retry, stop_after_attempt
import random

class CavesHandler:
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def __init__(self, Id=None):
        if Id is None:
            caves = session.query(Caves).all()
            random.shuffle(caves)
            self.query = caves[0] if caves else None
        else:
            self.query = session.query(Caves).filter_by(Id=Id).first()

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def get_cave(self) -> dict:
        """
        获取回声洞
        ---------
        返回的数据类型：:class:`dict` - 回声洞

        数据格式::

            # 返回的dict
            cave = {'id': id,           # 回声洞ID
                    'sender': sender,   # 回声洞发送者
                    'content': content} # 回声洞内容

            # 回声洞内容
            content = [{'text': '...',        # 文本消息内容
                       'image': <img_path>},  # 图片消息内容
                      ...]
                       
        """
        if self.query is None:
            return None
        content = json.loads(self.query.content)
        sender = self.query.sender
        id = self.query.Id
        cave = {'id': id, 'sender': sender, 'content': content}
        return cave

    def get_id(self) -> int:
        """
        获取新的回声洞id
        ---------------
        返回的数据类型：:class:`int` - 回声洞ID
        """
        self.query = session.query(Caves).order_by(Caves.Id.desc()).first()
        return self.query.Id + 1 if self.query is not None else 1
    
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def add_cave(self, cave: dict):
        """
        新增回声洞
        ---------
        输入的数据类型：:class:`dict` - 回声洞
        返回的数据类型：:class:`bool` - 回声洞是否添加成功

        数据格式::

            # 输入的dict
            cave = {'id': id,           # 回声洞ID
                    'sender': sender,   # 回声洞发送者
                    'content': content} # 回声洞内容

            # 回声洞内容
            content = [{'text': '...',       # 文本消息内容
                       'image': <img_path>}, # 图片消息内容
                      ...]
                       
        """
        self.query = session.query(Caves).order_by(Caves.Id.desc()).first()
        Id = cave['id']
        content = json.dumps(cave['content'])
        sender = cave['sender']
        session.add_all([Caves(Id=Id, content=content, sender=sender)])
        session.commit()
        session.expire_all()
        return True

    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def delete_cave(self, Id):
        """
        删除回声洞
        ---------
        输入的数据类型：:class:`int` - 回声洞ID
        返回的数据类型：:class:`bool` - 回声洞是否删除成功
        """
        delete_data = session.query(Caves).filter_by(Id=Id).delete()
        if delete_data:
            session.commit()
            session.expire_all()
            return True
        return False
    
    @retry(stop=stop_after_attempt(3), reraise=True)
    @auto_rollback_error
    def cave_list(self):
        """
        获取所有回声洞
        ------------
        返回的数据类型：:class:`list` - 回声洞列表

        数据格式::

            # 返回的list
            cave = [{'id': id,           # 回声洞ID
                    'sender': sender,    # 回声洞发送者
                    'content': content}, # 回声洞内容
                   ...]

            # 回声洞内容
            content = [{'text': '...',       # 文本消息内容
                       'image': <img_path>}, # 图片消息内容
                      ...]
                       
        """
        caves = session.query(Caves.Id).all()
        return caves if caves is not None else None
