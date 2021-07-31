from core.elements import MessageSession, Plain, Image as BImage, Session
from PIL import Image

from core.elements.others import confirm_command


class Template(MessageSession):
    all_func = ("Feature", "sendMessage", "waitConfirm", "asDisplay", "delete", "checkPermission", "Typing", "checkSuperUser")

    class Feature:
        image = True
        voice = False

    async def sendMessage(self, msgchain, quote=True) -> MessageSession:
        if isinstance(msgchain, str):
            print(msgchain)
            return MessageSession(target=self.target, session=Session(message=msgchain, target='TEST|Console', sender='TEST|Console'))
        if isinstance(msgchain, list):
            msg_list = []
            for x in msgchain:
                if isinstance(x, Plain):
                    print(x.text)
                    msg_list.append(x.text)
                if isinstance(x, BImage):
                    img = Image.open(x.image)
                    img.show()
            return MessageSession(target=self.target, session=Session(message=str(msg_list), target='TEST|Console', sender='TEST|Console'))

    async def waitConfirm(self):
        c = input('Confirm: ')
        if c in confirm_command:
            return True
        return False

    def asDisplay(self):
        return self.session.message

    async def delete(self):
        print(f"(Try to delete {self.session.message}, but I'm a console so I cannot do it :< )")
        return True

    def checkPermission(self):
        print(f"(Try to check your permissions, but this is a unit test environment. Have fun!)")
        return True

    def checkSuperUser(self):
        print(f"(Try to check if you are superuser, but this is a unit test environment. Have fun!)")
        return True

    class Typing:
        def __init__(self, msg: MessageSession):
            self.msg = msg

        async def __aenter__(self):
            print('Console is typing...')

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

