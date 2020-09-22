import traceback
def commandlist():
    clist = {}
    import os
    path = os.path.abspath('./modules')
    dirs = os.listdir(path)

    import re

    for file in dirs:
        filename = os.path.abspath(f'./modules/{file}')
        a1 = None
        a2 = None
        if os.path.isdir(filename):
            if file == '__pycache__':
                pass
            else:
                a1 = file
                a2 = file
        if os.path.isfile(filename):
            b = re.match(r'(.*)(.py)', file)
            if b:
                a1 = b.group(1)
                a2 = b.group(1)
        try:
            if a1 is not None:
                a = __import__('modules.' + a1, fromlist=[a2])
                if isinstance(a.command, dict):
                    clist.update(a.command)
                    print(f'Successful loaded {a2} from {a1}! command = {a.command}')
                elif isinstance(a.command, tuple):
                    for x in a.command:
                        if isinstance(x, dict):
                            clist.update(x)
                            print(f'Successful loaded {x.keys()}! command = {x}')
        except Exception as e:
            print(str(e) + ', skip!')
    return clist
