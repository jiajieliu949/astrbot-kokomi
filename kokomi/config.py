import os


class Plugin_Config:
    # 数据接口指定和默认配置
    API_URL = os.getenv('KOKOMI_API_URL', 'http://43.155.60.190:8000')
    API_TYPE = os.getenv('KOKOMI_API_TYPE', 'Bearer')
    API_USERNAME = os.getenv('KOKOMI_API_USERNAME', '')
    API_PASSWORD = os.getenv('KOKOMI_API_PASSWORD', '')
    REQUEST_TIMEOUT = 10
    # 默认触发关键词
    CN_START_WITH = 'wws'
    EN_START_WITH = '*'
    # 版本
    VERSON = '4.1.9'
    LOCAL_TIME_ZONE = 8
    # 返回图片的格式，请根据实际需求选择
    RETURN_PIC_TYPE = 'file'
    # 是否显示徽章
    SHOW_DOG_TAG = True                                                                                              
    SHOW_CLAN_TAG = True
    SHOW_CUSTOM_TAG = True
    BOT_INFO = {
        'en':f'Wows-Stats-Bot Kokomi-{VERSON}',
        'cn':f'Wows-Stats-Bot Kokomi-{VERSON}',
        'ja':f'Wows-Stats-Bot Kokomi-{VERSON}'
    }
    BOT_AUTHOR = 'Powered by Maoyu'
