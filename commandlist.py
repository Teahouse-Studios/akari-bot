def commandlist():
    clist = []
    import os
    path = os.path.abspath('./modules')
    dirs = os.listdir(path)

    import re

    for file in dirs:
        filename = os.path.abspath(f'./modules/{file}')
        if os.path.isdir(filename):
            if file == '__pycache__':
                pass
            else:
                a = __import__('modules.'+file, fromlist=[file])
                try:
                    if isinstance(a.command, str):
                        clist.append(a.command)
                    else:
                        for x in a.command:
                            clist.append(x)
                except:
                    pass
        if os.path.isfile(filename):
            b = re.match(r'(.*)(.py)', file)
            if b:
                a = __import__('modules.'+b.group(1), fromlist=[b.group(1)])
                try:
                    if isinstance(a.command, str):
                        clist.append(a.command)
                    else:
                        for x in a.command:
                            clist.append(x)
                except:
                    pass
    return clist
