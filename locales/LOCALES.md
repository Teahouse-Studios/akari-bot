# 简介

本文为多语言相关的规范文件，请按照此文件的要求设置多语言内容，以方便维护。

# 简体中文排版
> 本文部分参照[中文文案排版指北](https://github.com/sparanoid/chinese-copywriting-guidelines)，内容可能有出入。

## 空格
### 中英文之间需要增加空格。
正确：
> 在 LeanCloud 上，数据存储是围绕 `AVObject` 进行的。

错误：
> 在LeanCloud上，数据存储是围绕`AVObject`进行的。
> 
> 在 LeanCloud上，数据存储是围绕`AVObject` 进行的。

例外：「豆瓣FM」等产品名词，按照官方所定义的格式书写。

### 中文与数字之间需要增加空格。
正确：
  > 今天出去买菜花了 5000 元。

错误：
  > 今天出去买菜花了 5000元。
  >
  > 今天出去买菜花了5000元。

### 数字与单位之间不加空格
正确：
> 我家的光纤入屋宽带有 10Gbps，SSD 一共有 20TB
>
> 角度为 90° 的角，就是直角。
>
> 新 MacBook Pro 有 15% 的 CPU 性能提升。

错误：
> 我家的光纤入屋宽带有 10 Gbps，SSD 一共有 20 TB
>
> 角度为 90 ° 的角，就是直角。
>
> 新 MacBook Pro 有 15 % 的 CPU 性能提升。

### 全角标点与其他字符之间不加空格
正确：
> 刚刚买了一部 iPhone，好开心！

错误：
> 刚刚买了一部 iPhone ，好开心！
>
> 刚刚买了一部 iPhone， 好开心！

### 变量之间增加空格
正确：
> 请 [提交一个 issue](#) 并分配给相关同事。
>
> 访问我们网站的最新动态，请 [点击这里](#) 进行订阅！

错误：
> 请[提交一个 issue](#)并分配给相关同事。
>
> 访问我们网站的最新动态，请[点击这里](#)进行订阅！

## 标点符号
### 不重复使用标点符号
虽然中国大陆的标点符号用法允许重复使用标点符号，但是这样会破坏句子的美观性。

正确：
> 德国队竟然战胜了巴西队！
>
> 她竟然对你说「喵」？！

错误：
> 德国队竟然战胜了巴西队！！
>
> 德国队竟然战胜了巴西队！！！！！！！！
>
> 她竟然对你说「喵」？？！！
>
> 她竟然对你说「喵」？！？！？？！！

## 全角和半角
不明白什么是全角（全形）与半角（半形）符号？请查看维基百科条目『[全角和半角](https://zh.wikipedia.org/wiki/%E5%85%A8%E5%BD%A2%E5%92%8C%E5%8D%8A%E5%BD%A2)』。

### 使用全角中文标点
正确：
> 嗨！你知道嘛？今天前台的小妹跟我说「喵」了哎！
>
> 核磁共振成像（NMRI）是什么原理都不知道？JFGI！

错误：
> 嗨! 你知道嘛? 今天前台的小妹跟我说 "喵" 了哎！
>
> 嗨!你知道嘛?今天前台的小妹跟我说"喵"了哎！
>
> 核磁共振成像 (NMRI) 是什么原理都不知道? JFGI!
>
> 核磁共振成像(NMRI)是什么原理都不知道?JFGI!

例外：中文句子内夹有英文书籍名、报刊名时，不应借用中文书名号，应以英文斜体表示。

### 数字使用半角字符
正确：
> 这个蛋糕只卖 1000 元。

错误：
> 这个蛋糕只卖 １０００ 元。

例外：在设计稿、宣传海报中如出现极少量数字的情形时，为方便文字对齐，是可以使用全角数字的。

### 遇到完整的英文整句、特殊名词，其内容使用半角标点
正确：
> 乔布斯那句话是怎么说的？「Stay hungry, stay foolish.」
>
> 推荐你阅读 *Hackers & Painters: Big Ideas from the Computer Age*，非常地有趣。

错误：
> 乔布斯那句话是怎么说的？「Stay hungry，stay foolish。」
>
> 推荐你阅读《Hackers＆Painters：Big Ideas from the Computer Age》，非常的有趣。

### 简体中文不得使用直角引号
正确：
> “老师，‘有条不紊’的‘紊’是什么意思？”

错误：
> 「老师，『有条不紊』的『紊』是什么意思？」

## 名词
### 专有名词使用正确的大小写

正确：
> 使用 GitHub 登录
>
> 我们的客户有 GitHub、Foursquare、Microsoft Corporation、Google、Facebook, Inc.。

错误：
> 使用 github 登录
>
> 使用 GITHUB 登录
>
> 使用 Github 登录
>
> 使用 gitHub 登录
>
> 使用 gｲんĤЦ8 登录
>
> 我们的客户有 github、foursquare、microsoft corporation、google、facebook, inc.。
>
> 我们的客户有 GITHUB、FOURSQUARE、MICROSOFT CORPORATION、GOOGLE、FACEBOOK, INC.。
>
> 我们的客户有 Github、FourSquare、MicroSoft Corporation、Google、FaceBook, Inc.。
>
> 我们的客户有 gitHub、fourSquare、microSoft Corporation、google、faceBook, Inc.。
>
> 我们的客户有 gｲんĤЦ8、ｷouЯƧquﾑгє、๓เςг๏ร๏Ŧt ς๏гק๏гคtเ๏ภn、900913、ƒ4ᄃëв๏๏к, IПᄃ.。

### 不要使用不地道的缩写
正确：
> 我们需要一位熟悉 TypeScript、HTML5，至少理解一种框架（如 React、Next.js）的前端开发者。

错误：
> 我们需要一位熟悉 Ts、h5，至少理解一种框架（如 RJS、nextjs）的 FED。
