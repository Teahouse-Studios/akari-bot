from functools import reduce
from sympy import Symbol, solve
from typing import List
from loguru import logger

import re, collections


class Factor:
    def GetMaxFactor(self, num1, num2

                     ):
        if num1 < num2: num1, num2 = num2, num1
        while num2 != 0: num1, num2 = num2, num1 % num2
        return num1

    def LeastCommonMultiple(self, num1, num2) -> int:
        return num1 * num2 / self.GetMaxFactor(num1, num2)

    def NumsLCM(self, *args):
        return reduce(self.LeastCommonMultiple, args)


class fraction(Factor):

    def __init__(self, numerator=1, denominator

    =1, string=None):
        '''
        numerator\n
        ——————\n
        denominator
        '''
        if string:
            nums = string.split("/")
            self.numerator, self.denominator

=(nums) + [1] * (2 - len(nums))
else:self.numerator, self.denominator = numerator, denominator
self.numerator, self.denominator = int(self.numerator), int(self.denominator)
'''
chemlist_Nu=[[1,'氢','H',1],[2,'氦','He',4],[3,'锂','Li',7],[4,'铍','Be',9],[5,'硼','B',11],[6,'碳','C',12],[7,'氮','N',14],[8,'氧','O',16],\
    [9,'氟','F',19],[10,'氖','Ne',20],[11,'钠','Na',23],[12,'镁','Mg',24],[13,'铝','Al',27],[14,'硅','Si',28],[15,'磷','P',31],[16,'硫','S',32],\
    [17,'氯','Cl',35],[18,'氩','Ar',40],[19,'钾','K',39],[20,'钙','Ca',40],[26,'铁','Fe',56],[29,'铜','Cu',64],[30,'锌','Zn',65],[47,'银','Ag',\
    108],[53,'碘','I',127],[78,'铂','Pt',195],[79,'金','Au',197],[80,'汞','Hg',201]]
chemlist_Na={i[1]:[i[0],i[2],i[3]]for i in chemlist_Nu}#stand for Name
chemlist_Sy={i[2]:[i[0],i[1],i[3]]for i in chemlist_Nu}#stand for Symbol
chemlist_Ra={i[3]:[i[1],i[2],i[0]]for i in chemlist_Nu}#stand for R(a)
chemlist_Nu={i[0]:[i[1],i[2],i[3]]for i in chemlist_Nu}#stand for Number
'''
vals = 'abcdefghigklmnopqrstuvwxyz'
chemlist_Nu = {1: ['氢', 'H', 1], 2: ['氦', 'He', 4], 3: ['锂', 'Li', 7], 4: ['铍', 'Be', 9], 5: ['硼', 'B', 11],
               6: ['碳', 'C', 12], 7: ['氮', 'N', 14], 8: ['氧', 'O', 16], 9: ['氟', 'F', 19], 10: ['氖', 'Ne', 20],
               11: ['钠', 'Na', 23], 12: ['镁', 'Mg', 24], 13: ['铝', 'Al', 27], 14: ['硅', 'Si', 28],
               15: ['磷', 'P', 31], 16: ['硫', 'S', 32], \
               17: ['氯', 'Cl', 35.5], 18: ['氩', 'Ar', 40], 19: ['钾', 'K', 39], 20: ['钙', 'Ca', 40],
               26: ['铁', 'Fe', 56], 29: ['铜', 'Cu', 64], 30: ['锌', 'Zn', 65], 47: ['银', 'Ag', 108],
               53: ['碘', 'I', 127], 78: ['铂', 'Pt', 195], 79: ['金', 'Au', 197], 80: ['汞', 'Hg', 201]}
chemlist_Na = {'氢': [1, 'H', 1], '氦': [2, 'He', 4], '锂': [3, 'Li', 7], '铍': [4, 'Be', 9], '硼': [5, 'B', 11],
               '碳': [6, 'C', 12], '氮': [7, 'N', 14], '氧': [8, 'O', 16], '氟': [9, 'F', 19], '氖': [10, 'Ne', 20],
               '钠': [11, 'Na', 23], '镁': [12, 'Mg', 24], '铝': [13, 'Al', 27], '硅': [14, 'Si', 28],
               '磷': [15, 'P', 31], '硫': [16, 'S', 32], \
               '氯': [17, 'Cl', 35.5], '氩': [18, 'Ar', 40], '钾': [19, 'K', 39], '钙': [20, 'Ca', 40],
               '铁': [26, 'Fe', 56], '铜': [29, 'Cu', 64], '锌': [30, 'Zn', 65], '银': [47, 'Ag', 108],
               '碘': [53, 'I', 127], '铂': [78, 'Pt', 195], '金': [79, 'Au', 197], '汞': [80, 'Hg', 201]}
chemlist_Sy = {'H': [1, '氢', 1], 'He': [2, '氦', 4], 'Li': [3, '锂', 7], 'Be': [4, '铍', 9], 'B': [5, '硼', 11],
               'C': [6, '碳', 12], 'N': [7, '氮', 14], 'O': [8, '氧', 16], 'F': [9, '氟', 19], 'Ne': [10, '氖', 20],
               'Na': [11, '钠', 23], 'Mg': [12, '镁', 24], 'Al': [13, '铝', 27], 'Si': [14, '硅', 28],
               'P': [15, '磷', 31], 'S': [16, '硫', 32], \
               'Cl': [17, '氯', 35.5], 'Ar': [18, '氩', 40], 'K': [19, '钾', 39], 'Ca': [20, '钙', 40],
               'Fe': [26, '铁', 56], 'Cu': [29, '铜', 64], 'Zn': [30, '锌', 65], 'Ag': [47, '银', 108],
               'I': [53, '碘', 127], 'Pt': [78, '铂', 195], 'Au': [79, '金', 197], 'Hg': [80, '汞', 201]}
chemlist_Ra = {1: ['氢', 'H', 1], 4: ['氦', 'He', 2], 7: ['锂', 'Li', 3], 9: ['铍', 'Be', 4], 11: ['硼', 'B', 5],
               12: ['碳', 'C', 6], 14: ['氮', 'N', 7], 16: ['氧', 'O', 8], 19: ['氟', 'F', 9], 20: ['氖', 'Ne', 10],
               23: ['钠', 'Na', 11], 24: ['镁', 'Mg', 12], 27: ['铝', 'Al', 13], 28: ['硅', 'Si', 14],
               31: ['磷', 'P', 15], 32: ['硫', 'S', 16], \
               35: ['氯', 'Cl', 17], 40: ['钙', 'Ca', 20], 39: ['钾', 'K', 19], 56: ['铁', 'Fe', 26],
               64: ['铜', 'Cu', 29], 65: ['锌', 'Zn', 30], 108: ['银', 'Ag', 47], 127: ['碘', 'I', 53],
               195: ['铂', 'Pt', 78], 197: ['金', 'Au', 79], 201: ['汞', 'Hg', 80]}


def get(Obj: object) -> tuple:
    return Obj.get()


def Replace(string: str, lister: list) -> str:
    s = string
    for i in lister: s = s.replace(i[0], i[1])
    return s


class chem:
    def __init__(self, string):
        '''
        From string to 化学式
        '''

        def GetMr(dic: dict) -> int:
            '''
            Special method,just for class chem,to get Mr of the chemical


            '''
            return sum(chemlist_Sy[i][2] * k for i, k in dic.items()), [chemlist_Sy[i][2] * k for i, k in dic.items()]

        def GetDis(formula: str) -> dict:
            '''
            From string to 化学式
            '''
            # ()标记一个子表达式的开始和结束位置 每一组括号意味着返回单独一个匹配条件的元组 |指明两项之间的一个选择,意义为或.
            # 在下式中,两个|就是数字左右括号三选一 5个()意味着每个子表达式会返回包含5个元素（至少1个不为空）的匹配元组

            parse = re.findall(r"([A-Z][a-z]*)(\d*)|(\()|(\))(\d*)", formula)
            stack = [collections.Counter()]  # 使用collections.Counter()避免造轮子以及通过其特性/数据结构来减少代码行数

            # name 元素 m1 紧邻其后的元素数量 left/right 左、右括号 m2 右括号之后的数字,即factor 基于输入为真实的表达式,所以没有一些错误检测
            for name, m1, left_open, right_open, m2 in parse:
                if name: stack[-1][name] += int(m1 or 1)
                # Counter的结构特性,当Counter中不存在name时,"+="会被视作"=",因此简化代码.元素存在,加1；不存在,初始化为1.由于Counter的特性,“+=” 同时满足“加”和“初始化”
                if left_open: stack.append(collections.Counter())  # 由内而外,不用在这循环.从第一个右括号开始,所以是由内而外.
                if right_open:  # 括号内的元素乘右括号后的系数,系数存在时必大于1
                    top = stack.pop()
                    for k in top: stack[-1][k] += top[k] * int(m2 or 1)
            return (dict(stack[0]))
            # fraction

        self.chemformula = GetDis


(string)
self.Mr, self.m = GetMr(self.chemformula)
Gs = [["NH4", "A"], ['CO3', 'B'], ['NO3', 'C'], ['SO4', 'D'], ['PO4', 'E'], ['OH', 'F']]
atoms = GetDis(Replace(string, Gs))
self.AtomGroup = {i[0]: atoms.get(i[1], 0) for i in Gs}
self.string = string


def get(self, *args): return self.chemformula, self.Mr, self.AtomGroup


def __str__(self):
    return self.string


def LaTex(self):
    k = ''

    for i in range(len(self.string) - 1):
        k += self.string[i]
        if self.string[i + 1].isdigit() and not (self.string[i].isdigit()): k += '_{'
        if self.string[i].isdigit() and not (self.string[i + 1].isdigit()): k += '}'
    ans = k + self.string[-1]
    return ans if not self.string[-1].isdigit() else ans + "}"


class ChemicalEquation:

    def __init__(self, left: List[chem], right: List[chem], condition: str):
        # make first as 1|
        #               V make symbols
        lefts, rights = [1] + [Symbol(i) for i in vals[:len(left) - 1

                                                  ]], [Symbol(i) for i in
                                                       vals[len(left) - 1:len(right) - 1 + len(left)]]

        def GetAllAtoms(From):
            a = set()
            for i in From: a.update(list(i.chemformula.keys()))
            return a

        def GetNumAtoms(AtomName, FromList: List[dict], SymList: List[Symbol]):
            return sum(FromList[i].chemformula.get(AtomName, 0) * SymList[i] for i in range(len(FromList)))

        LeftAtoms, RightAtom = [GetNumAtoms(i, left, lefts) for i in GetAllAtoms(left)], [GetNumAtoms(i, right, rights)
                                                                                          for i in GetAllAtoms(right)]
        result = solve([LeftAtoms[i] - RightAtom[i] for i in range(len(LeftAtoms))], *lefts[1:] + rights)  # eqs,sys
        if not all([str(type(i)) == "<class 'sympy.core.numbers.Integer'>" for i in result.values()]):  # if all int?
            fractions

=[fraction(1, 1)] + [fraction(string=str(i)) for i in result.values()]
LCM = Factor().NumsLCM(*[i.denominator for i in fractions])  # get LCM
result = [int(fraction(fractions[i].numerator * LCM, denominator=fractions[i].denominator)) for i in
          range(len(fractions))]  # all to Integer
else:result = list(result.values())
self.left, self.right, self.lefts, self.rights, self.condition = left, right, result[:len(left)], result[
                                                                                                  len(left):], condition  # make self.vals


def __str__(self):
    ans = ''
    for x in [[self.left, self.lefts, 0], [self.right, self.rights, 1]]:
        right = ''
        for i in range(len(x[1])): right += f" + {str(x[1][i]) if x[1][i] != 1 else ''}" + str(x[0][i])
        ans += right[2:]
        if x[2] == 1: break
        ans += f"={self.condition}="
    return ans


def LaTex(self):
    x, y, z = str(self).split('=')
    x, y, z = "{" + x, "{" + y + "}", z + "}"
    return f"\\ce {x} \\xlongequal{y} {z}"


def Str2Equ(string: str) -> ChemicalEquation:
    s = string.split('=')
    return ChemicalEquation([chem(i) for i in s[0].split('+')], [chem(i) for i in s[2].split("+")], s[1])

