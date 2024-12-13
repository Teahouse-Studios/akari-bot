request_by_web_render_list = [  # re.compile(r'.*minecraft\.wiki'),  # sigh
    # re.compile(r'.*runescape\.wiki'),
]

generate_screenshot_v2_blocklist = ['https://mzh.moegirl.org.cn', 'https://zh.moegirl.org.cn']

special_namespace_list = ['special', '特殊']

random_title_list = ['random', '随机页面', '隨機頁面']

redirect_list = {'https://zh.moegirl.org.cn/api.php': 'https://mzh.moegirl.org.cn/api.php',  # 萌娘百科强制使用移动版 API
                 'https://minecraft.fandom.com/api.php': 'https://minecraft.wiki/api.php',  # no more Fandom then
                 'https://minecraft.fandom.com/zh/api.php': 'https://zh.minecraft.wiki/api.php'
                 }

special_talk_page_class = {
    'https://zh.minecraft.wiki/api.php': [
        'page-Minecraft_Wiki_社区专页',
        'page-Minecraft_Wiki_管理员告示板',

    ],
    'https://minecraft.wiki/api.php': [
        'page-Minecraft_Wiki_Admin_noticeboard'
    ],
}

forum_class = {
    'https://zh.minecraft.wiki/api.php': [
        'page-Minecraft_Wiki_论坛',

    ],
    'https://minecraft.wiki/api.php': [
        'page-Minecraft_Wiki_Forum'
    ],
    'https://pt.minecraft.wiki/api.php': [
        'page-Minecraft_Wiki_Fórum'
    ],
    'https://es.minecraft.wiki/api.php': [
        'page-Minecraft_Wiki_Foro'
    ]

}
