import re
import os
import json
import random
from .common import (
    picture,
    get_bind,
    wws_lang,
    wws_error,
    wws_message
)
from .config import Plugin_Config
from .path import plugin_path
from .lang.select_func_cn import main as main_cn
from .lang.select_func_en import main as main_en
from .lang.select_func_ja import main as main_ja

file_path = os.path.join(plugin_path, 'json', f'special_msg.json')
file_json = open(file_path, "r", encoding="utf-8")
json_data = json.load(file_json)
file_json.close() 

class select_funtion:
    async def main(
        msg:list,
        user_id:str,
        user_data:dict,
        platform:str,
        platform_id:str,
        channel_id:str,
        platform_data:dict
    ):
        author_id_list = json_data['special_id_list']
        author_msg = json_data['special_msg']
        if user_id in author_id_list and msg[0] in author_msg:
            return {
                'type': 'msg',
                'msg': random.choice(author_msg.get(msg[0],'mua')),
                'img': None
            }
        if msg == ['kokomi'] or msg == [] or msg is None:
            return {
                'type': 'msg',
                'msg': 'kokomi在哦，请问找我有什么事嘛~',
                'img': None
            }
        # 处理消息
        if msg[0] == Plugin_Config.CN_START_WITH:
            del msg[0]
        if msg == ['kokomi'] or msg == [] or msg is None:
            return {
                'type': 'msg',
                'msg': 'kokomi在哦，请问找我有什么事嘛~',
                'img': None
            }
        if (
            # qqgroup
            msg[0].startswith('[CQ:at,qq=') and
            msg[0].endswith(']')
        ) or (
            # qqguild
            msg[0].startswith('<@!') and
            msg[0].endswith('>')
        ):
            user_id = (re.findall(r'\d+', msg[0]))[0]
            msg[0] = 'me'
        if Plugin_Config.EN_START_WITH == msg[0]:
            del msg[0]
        if Plugin_Config.EN_START_WITH in msg[0]:
            msg[0] = msg[0].replace(Plugin_Config.EN_START_WITH,'')
        # 获取用户绑定信息
        bind_data = await get_bind.get_bind_data(
            platform=platform,
            uid=user_id
        )
        default_lang = wws_lang.get_default_lang(
            platform=platform,
            platform_id=platform_id,
            channel_id=channel_id
        )
        pic_num = picture.get_pic(id=user_id)
        if (
            bind_data['status'] == 'ok' and 
            bind_data['message'] == 'NO BIND DATA'
        ):
            aid=None
            server=None
            use_pr=True
            lang=default_lang
            use_ac=False
            ac=None
        elif (
            bind_data['status'] != 'ok' and
            bind_data['message'] != 'SUCCESS'
        ):
            return select_funtion.return_data(
                result=bind_data,
                lang=default_lang,
                pic_num = pic_num
            )
        else:
            aid=bind_data['data']['aid']
            server=bind_data['data']['server']
            use_pr=bind_data['data']['use_pr']
            lang=bind_data['data']['lang']
            use_ac=bind_data['data']['use_ac']
            ac=bind_data['data']['ac']
            if lang != 'cn' and pic_num != 1:
                pic_num = 1
        if lang == 'cn':
            select_result = await main_cn(
                msg=msg,
                user_id=user_id,
                user_data=user_data,
                platform=platform,
                platform_id=platform_id,
                channel_id=channel_id,
                platform_data=platform_data,
                pic_num = pic_num,

                aid=aid,
                server=server,
                use_pr=use_pr,
                lang=lang,
                use_ac=use_ac,
                ac=ac
            )
        elif lang == 'en':
            select_result = await main_en(
                msg=msg,
                user_id=user_id,
                user_data=user_data,
                platform=platform,
                platform_id=platform_id,
                channel_id=channel_id,
                platform_data=platform_data,
                pic_num = pic_num,

                aid=aid,
                server=server,
                use_pr=use_pr,
                lang=lang,
                use_ac=use_ac,
                ac=ac
            )
        elif lang == 'ja':
            select_result = await main_ja(
                msg=msg,
                user_id=user_id,
                user_data=user_data,
                platform=platform,
                platform_id=platform_id,
                channel_id=channel_id,
                platform_data=platform_data,
                pic_num = pic_num,

                aid=aid,
                server=server,
                use_pr=use_pr,
                lang=lang,
                use_ac=use_ac,
                ac=ac
            )
        if select_result['status'] == 'ok' and select_result['message'] == 'SUCCESS':
            function = select_result['function']
            # ★ 候选选号拦截（2026-10-16）：parameter 带第 4 项 pick_meta 时，
            #   不渲染候选图，返回候选结构由 AstrBot 侧注册「回复序号」交互。
            _params = select_result.get('parameter') or []
            if (len(_params) >= 4 and isinstance(_params[3], dict)
                    and _params[3].get('pick_meta')):
                return {
                    'status': 'ok',
                    'message': 'SUCCESS',
                    'type': 'pick_candidates',
                    'lang': _params[0],
                    'ships': _params[1],
                    'aid': _params[3].get('aid'),
                    'server': _params[3].get('server'),
                }
            result = await function(select_result['parameter'])
        else:
            result = select_result
        return select_funtion.return_data(
            result=result,
            lang=lang,
            pic_num = pic_num
        )
        
    def return_data(
        result:dict,
        lang:str,
        pic_num:int
    ):
        if result['status'] == 'ok' and result['message'] == 'SUCCESS':
            return {
                'type': 'img',
                'msg': None,
                'img': result['img']
            }
        elif result['status'] == 'ok' and result['message'] != 'SUCCESS':
            return_msg = wws_message.main(
                result=result,
                lang=lang
            )
            return {
                'type': 'msg',
                'msg': return_msg,
                'img': None
            }
        else:
            return_img = wws_error.main(
                result=result,
                lang=lang,
                pic_num=pic_num
            )
            return {
                'type': 'img',
                'msg': None,
                'img': return_img['img']
            }
    


        