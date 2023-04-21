import os

import ujson as json

with open(os.path.dirname(os.path.abspath(__file__)) + '/dataset.txt', 'r', encoding='utf-8') as f:
    txt = f.read()

txt = txt.splitlines()
txt = [x for x in txt if x != '']

with open(os.path.dirname(os.path.abspath(__file__))+'/dataset.jsonl', 'w', encoding='utf-8') as f:
    for i in range(0, len(txt), 2):
        f.write(json.dumps({'prompt': f'{txt[i]}\n\n###\n\n', 'completion': f' {txt[i + 1]}\n'}, ensure_ascii=False))
        f.write('\n')
