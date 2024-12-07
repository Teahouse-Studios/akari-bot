import logging
import re
import time

from base64 import urlsafe_b64encode
from typing import Dict
from urllib.parse import unquote

from mail_gw import Account as TempMail
from requests import Session

from .utils import generate_random_string


class Account:
    logged_in: bool = False  # 是否已登录
    email: str = None  # 当前好分数账号邮箱地址
    password: str = None  # 当前好分数账号密码
    session: Session = None  # requests会话
    __account_data: dict = None  # 当前学生信息
    __exams_data: list = None  # 考试列表

    def __init__(self, log: bool = False, proxies=None):
        # 初始化session
        self.session = Session()

        # 配置代理
        if type(proxies) == str:
            self.session.proxies = {'http': proxies, 'https': proxies}
        elif type(proxies) == dict:
            self.session.proxies = proxies
        self.session.headers.update({
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36',
            'Origin': 'https://www.haofenshu.com',
            'Referer': 'https://www.haofenshu.com/',
        })

        # 配置日志
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level=logging.INFO if log else logging.WARNING)
        if not self.logger.handlers:
            console = logging.StreamHandler()
            console.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(console)

    def login(self, email, password):
        '''
            直接登录已有账号（必须是学生版）
            @param email: 邮箱地址
            @param password: 密码
        '''
        r = self.session.post(
            'https://hfs-be.yunxiao.com/v2/users/sessions',
            data={
                'loginName': email,
                'password': password,
                'rememberMe': 2,
                'roleType': 1
            },
        )
        self.email = email
        self.password = password
        self.logged_in = r.status_code == 200
        self.logger.info(f'邮箱：{email} 登录结果：{r.status_code}')

    def register(self,
                 studentName,
                 xuehao,
                 schoolName: str = None,
                 password: str = None,
                 max_retry: int = 5):
        '''
            提供学生姓名和学号，自动使用临时邮箱注册、验证并登录好分数账号，返回生成账号的邮箱地址和密码。
            @param studentName: 学生姓名
            @param xuehao: 学号
            @param schoolName: 学校名称，可不填，用于对重名重学号的学生进行区分，若要填写请务必先抓包确认学校名称是否正确！
            @param password: 指定生成的学生账号设置的密码，可不填，若不填则自动生成随机密码
            @param max_retry: 最大重试次数，若注册失败则会重试，直到达到最大重试次数为止
            返回值：元组(邮箱地址，密码)
        '''
        if password is None:
            password = generate_random_string(8)
        # 查找学生
        r = self.session.get(
            'https://hfs-be.yunxiao.com/v2/users/matched-students',
            params={
                'roleType': '1',
                'identityType': '1',
                'identityCode': xuehao,
                'studentName': studentName
            }).json()
        studentId = None
        if schoolName:
            for i in r['data']['students']:
                if schoolName in i['schoolName']:
                    studentId = i['studentId']
                    break
            assert studentId, '匹配学生失败：未找到符合条件的学生'
        else:
            assert len(r['data']['students']) > 0, '匹配学生失败：未找到符合条件的学生'
            assert len(
                r['data']
                ['students']) == 1, '匹配学生失败：找到多个符合条件的学生，分别来自 ' + ' '.join(
                    [f'[{i["schoolName"]}]'
                     for i in r['data']['students']]) + ' ，请指定学校名称。'
            studentId = r['data']['students'][0]['studentId']
            schoolName = r['data']['students'][0]['schoolName']
        self.logger.info(f'匹配学生成功：来自{schoolName}的{studentId}')

        self.logger.info('开始获取临时邮箱账号...')
        temp_mail = TempMail('hfs' + xuehao + generate_random_string(6),
                             password)
        self.logger.info(f'成功获取临时邮箱账号[{temp_mail.address}]，开始好分数注册...')
        r = self.session.post(
            'https://hfs-be.yunxiao.com/v2/native-users/verification-email',
            data={
                'email': temp_mail.address,
                'password': password,
                'roleType': 1
            },
        )
        assert r.status_code == 200, '注册失败：' + r.text

        self.logger.info(f'已在好分数注册成功，将在5秒后尝试获取验证邮件...')

        # 获取验证邮件并验证
        time.sleep(5)
        r = None
        retry = 0
        while retry < max_retry:
            try:
                r = temp_mail.get_message()
                break
            except IndexError:
                self.logger.info('验证邮件获取失败，将在5秒后重试...')
                time.sleep(5)
                retry += 1
        else:
            self.logger.warning(f'验证邮件获取失败，已达到最大重试次数，注册失败。')
            return None, None
        self.logger.info(f'验证邮件获取成功，开始验证...')

        ver_url = re.findall(r'>(http://www.haofenshu.com/.*?)<', r['html'][0])
        ver_code = re.findall(r'mailToken=(.*?)&', ver_url[0])[0]
        ver_code = unquote(ver_code, 'utf-8')
        r = self.session.post(
            'https://hfs-be.yunxiao.com/v2/native-users/activation',
            data={
                'deviceType': 3,
                'verificationType': 1,
                'verificationEmailToken': ver_code,
            },
        )
        self.email = temp_mail.address
        self.password = password

        self.logger.info(f'验证成功，开始绑定学生...')

        # 绑定学生
        r = self.session.put(
            'https://hfs-be.yunxiao.com/v2/users/bind-student',
            data={
                'identityCode': xuehao,
                'identityType': '1',
                'studentId': studentId
            },
        )

        self.logged_in = True
        self.logger.info(f'注册并绑定成功，账号为{self.email}，密码为{self.password}')
        return self.email, self.password

    def __get_account_data(self):
        assert self.logged_in, '获取学生信息前请先登录账号！'
        if self.__account_data is None:
            self.logger.info(f'未找到缓存，正在联网获取{{{self.email}}}账号的student信息...')
            r = self.session.get(
                'https://hfs-be.yunxiao.com/v2/user-center/user-snapshot'
            ).json()
            self.__account_data = r['data']

    @property
    def student(self):
        '''
            获取当前学生信息。首次取值时会自动获取并缓存。
            @return studentId: 学生ID（好分数生成的唯一ID，不同于学号）
            @return studentName: 学生姓名
            @return schoolName: 学校名称
            @return xuehao: 学号
            @return grade: 年级
            @return className: 班级（导师姓名）
        '''
        self.__get_account_data()

        data = {
            i: self.__account_data['linkedStudent'].get(i,'NaN')
            for i in ('studentId', 'studentName', 'schoolName', 'grade',
                      'className', 'xuehao')
        }
        data['xuehao'] = data['xuehao'][0]
        return data

    @property
    def is_member(self):
        '''
            判断当前账号是否为会员。
            @return (Bool)
        '''
        self.__get_account_data()

        return self.__account_data['isMember']

    @property
    def exams(self):
        '''
            获取当前学生的考试列表。首次取值时会自动获取并缓存。
        '''
        assert self.logged_in, '获取考试列表前请先登录账号！'
        if self.__exams_data is None:
            self.logger.info(f'未找到缓存，正在联网获取{{{self}}}的exams信息...')
            r = self.session.get(
                'https://hfs-be.yunxiao.com/v3/exam/list?start=-1').json()
            self.__exams_data = r['data']['list']
        return self.__exams_data

    def get_exam(self, latest=0):
        '''
            获取当前学生最近的第latest次考试，默认为最近一次考试。
            @param latest: 要获取的考试编号（0表示最近的一次，1表示第二近的一次，以此类推），默认为最近一次考试。
        '''
        assert self.logged_in, '获取考试详情前请先登录账号！'
        return Exam(self, self.exams[latest]['examId'])

    def get_exam_by_id(self, examId):
        '''
            @param examId: 要获取的考试ID（由好分数生成）。
        '''
        assert self.logged_in, '获取考试详情前请先登录账号！'
        return Exam(self, examId)

    def __str__(self):
        '''
            示例值：'12345678-张三' 或 '未登录'
        '''
        if self.logged_in:
            return f'{self.student["xuehao"]}-{self.student["studentName"]}'
        else:
            return '未登录'


class IncludeAccount:
    account: Account = None  # 所属账号
    logger: logging.Logger = None  # 日志记录器

    @property
    def session(self):
        return self.account.session

    @property
    def logger(self):
        return self.account.logger


class Paper(IncludeAccount):
    pictures: list


class Exam(IncludeAccount):
    examId: int = None  # 考试ID
    full_data: dict = None  # 考试详细数据
    papers: Dict[str, Paper]
    __papers_data: Dict[str, Paper] = None  # 考试试卷数据字典，key为试卷名称，value为试卷对象

    def __init__(self, account: Account, examId: int):
        '''
            初始化考试对象，自动获取考试详情。
            @param account: 账号对象
            @param examId: 考试编号
        '''
        self.account = account
        self.examId = examId
        r = self.session.get(
            f'https://hfs-be.yunxiao.com/v3/exam/{examId}/overview').json()
        self.full_data = r['data']
        self.logger.info(f'Exam对象{{{self}}}初始化成功。')

    @property
    def data(self):
        '''
            获取考试详细数据的精简信息。
        '''
        if self.full_data is None:
            return None
        return {
            i: self.full_data.get(i,'NaN')
            for i in (
                'examId',
                'name',
                'manfen',
                'manfenBeforeGrading',
                'score',
                'scoreBeforeGrading',
                'classRank',
                'gradeRank',
                'classRankPart',
                'gradeRankPart',
            )
        }

    @property
    def papers(self):
        '''
            获取考试的试卷信息。首次取值时会自动获取并缓存。
            返回值为一个字典，key为试卷名称，value为试卷对象。
        '''
        if self.__papers_data is None:
            self.logger.info(f'未找到缓存，正在联网获取{{{self}}}的papers信息...')
            self.__papers_data = {}
            for i in self.full_data['papers']:
                self.__papers_data[i['name']] = Paper(self, i)
        return self.__papers_data

    def __str__(self):
        '''
            示例值：'[12345678-张三]秋季学期期末考试'
        '''
        return f'[{self.account}]{self.full_data["name"]}'


class Paper(IncludeAccount):
    exam: Exam = None  # 试卷所属考试
    paperData: dict = None  # 试卷详细数据
    paperId: int = None  # 试卷ID
    __questions_data: list = None  # 试卷题目数据列表
    __pictures_data: list = None  # 答题卡图片URL列表

    def __init__(self, exam: Exam, paperData: dict):
        self.exam = exam
        self.account = exam.account
        self.paperData = paperData
        self.paperId = paperData['paperId']

    @property
    def questions(self):
        '''
            获取试卷的题目列表。首次取值时会自动获取并缓存。
            该接口返回好分数原生数据，未进行优化，实用性不高。
        '''
        if self.__questions_data is None:
            r = self.session.get(
                f'https://hfs-be.yunxiao.com/v3/exam/{self.exam.examId}/papers/{self.paperId}/question-detail'
            ).json()
            self.__questions_data = r['data']['questionList']
        return self.__questions_data

    @property
    def pictures(self):
        '''
            获取答题卡的图片列表。首次取值时会自动获取并缓存。
            返回值：一个列表，每个元素为字符串，表示图片URL。
        '''
        if self.__pictures_data is None:
            self.logger.info(f'未找到缓存，正在联网获取{{{self}}}的pictures信息...')
            r = self.session.get(
                f'https://hfs-be.yunxiao.com/v3/exam/{self.exam.examId}/papers/{self.paperId}/answer-picture'
            ).json()
            self.__pictures_data = r['data']['url']
        return self.__pictures_data

    def save_pictures(self, path: str):
        '''
            保存该试卷所有答题卡的图片到指定路径。
            @param path: 文件保存路径
            文件命名格式：
        '''
        for i in range(len(self.pictures)):
            self.logger.info(f'正在保存图片[{self.paperData["name"]}-{i+1}.png]...')
            r = self.session.get(self.pictures[i])
            with open(f'{path}/{self.paperData["name"]}-{i+1}.png', 'wb') as f:
                f.write(r.content)

    def __str__(self):
        '''
            示例值：'{[12345678-张三]秋季学期期末考试}-语文'
        '''
        return f'{{{self.exam}}}-{self.paperData["name"]}'


if __name__ == '__main__':
    ...
