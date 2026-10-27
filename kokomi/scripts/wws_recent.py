import os
import gc
from PIL import Image
from .. import (
    Plugin_Config,
    Picture,
    Game_Data,
    Text_Data,
    Box_Data,
    call_api,
    dog_tag,
    time_zone,
    write_error,
    fonts,
    plugin_path
)

async def main(
    parameter: list,
) -> dict:
    result = await get_data(
        parameter=parameter
    )
    return result

async def get_data(
    parameter: list,
) -> dict:
    # [aid server lang battle_type start_date end_date user_pr use_ac ac pic]
    try:
        path = '/r1/recent-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
            'lang':parameter[2],
            'battle_type':parameter[3],
            'start_date':parameter[4],
            'end_date': parameter[5],
            'use_pr':parameter[6],
            'use_ac': parameter[7],
            'ac': parameter[8]
        }
        if parameter[7] is False:
            del params['use_ac']
            del params['ac']
        res = await call_api.call_api(
            params=params,
            path=path
        )
        if (
            res['status'] != 'ok' or 
            res['message'] != 'SUCCESS'
        ):
            return res
        res_img = get_png(
            result=res,
            aid=parameter[0],
            server=parameter[1],
            lang=parameter[2],
            pic_num=parameter[9]
        )
        result = Picture.return_img(img=res_img)
        del res_img
        gc.collect()
        return result
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        track_id = write_error(
            error_file=__file__,
            error_params=parameter,
            error_name=str(type(e).__name__),
            error_info=error_info
        )
        return {
            'status': 'error', 
            'message': 'PROGRAM ERROR', 
            'error':f'{str(type(e).__name__)}', 
            'track_id': f'{track_id}'
        }
    finally:
        gc.collect()


def get_png(
    result: dict,
    aid: str,
    server: str,
    lang: str,
    pic_num: int
) -> str:
    text_list = []
    box_list = []
    bg_png_dict = {
        2: 'background_1',
        3: 'background_2',
        4: 'background_3'
    }
    list_png_dict = {
        2: 'list_1',
        3: 'list_2',
        4: 'list_3'
    }
    bg_png = bg_png_dict.get(pic_num,'background')
    list_png = list_png_dict.get(pic_num,'list')
    res_img_path = os.path.join(plugin_path, 'png', f'bg_{lang}', bg_png, 'wws_recent.png')
    bg_img = Image.open(res_img_path)
    list_png_len = int(result['data']['data_num'] / 50) + 1
    list_img_path = os.path.join(plugin_path, 'png', 'list', list_png, '80_50.png')
    list_img = Image.open(list_img_path)
    res_img = Image.new(
        mode='RGBA',
        size=(2428,2014+4500*list_png_len),
        color='white'
    )
    res_img.paste(bg_img, (0, 0))
    for i in range(list_png_len):
        res_img.paste(list_img, (0, 2014+4500*i))
    del list_img
    text_list.append(
        Text_Data(
            xy=(172, 161),
            text=result['nickname'],
            fill=(0, 0, 0),
            font_index=1,
            font_size=100
        )
    )
    text_list.append(
        Text_Data(
            xy=(199, 275),
            text=f'{server.upper()} -- {aid}',
            fill=(163, 163, 163),
            font_index=1,
            font_size=45
        )
    )
    fontStyle = fonts.data[1][55]
    if result['data']['clans']['clan_tag'] != 'None':
        tag = '['+str(result['data']['clans']['clan_tag'])+']'
    else:
        tag = str(result['data']['clans']['clan_tag'])
    tag_color = Picture.hex_to_rgb(result['data']['clans']['clan_color'])
    battle_type = result['data']['pr']['battle_type']
    if lang == 'cn':
        text_1 = '所属工会:'
        w_1 = Picture.x_coord(text_1, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 358),
                text=text_1,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        text_list.append(
            Text_Data(
                xy=(169+w_1+30, 358),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        text_2 = '数据类型:'
        w_2 = Picture.x_coord(text_2, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 448),
                text=text_2,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        battle_type_dict = {
            'pvp':'随机',
            'pvp_solo': '随机（单野）',
            'pvp_div2':'随机（双排）',
            'pvp_div3':'随机（三排）',
            'rank':'排位'
        }
        text_list.append(
            Text_Data(
                xy=(169+w_2+30, 448),
                text=battle_type_dict[battle_type],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        text_1 = 'User\'s Clan:'
        w_1 = Picture.x_coord(text_1, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 358),
                text=text_1,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        text_list.append(
            Text_Data(
                xy=(169+w_1+30, 358),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        text_2 = 'Data Type:'
        w_2 = Picture.x_coord(text_2, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 448),
                text=text_2,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        text_list.append(
            Text_Data(
                xy=(169+w_2+30, 448),
                text=battle_type.upper(),
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'ja':
        text_1 = 'クラン:'
        w_1 = Picture.x_coord(text_1, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 358),
                text=text_1,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        text_list.append(
            Text_Data(
                xy=(169+w_1+30, 358),
                text=tag,
                fill=tag_color,
                font_index=1,
                font_size=55
            )
        )
        text_2 = 'データです:'
        w_2 = Picture.x_coord(text_2, fontStyle)
        text_list.append(
            Text_Data(
                xy=(169, 448),
                text=text_2,
                fill=(72, 72, 72),
                font_index=1,
                font_size=55
            )
        )
        battle_type_dict = {
            'pvp':'ランダム戦',
            'pvp_solo': 'ランダム戦（SOLO）',
            'pvp_div2':'ランダム戦（DIV2）',
            'pvp_div3':'ランダム戦（DIV3）',
            'rank':'ランク戦'
        }
        text_list.append(
            Text_Data(
                xy=(169+w_2+30, 448),
                text=battle_type_dict[battle_type],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    battle_type = result['data']['pr']['battle_type']
    pr_png = result['data']['pr']['avg_pr_index']
    pr_png_path = os.path.join(plugin_path, 'png', f'bg_{lang}', 'pr', '{}.png'.format(pr_png))
    pr_png = Image.open(pr_png_path)
    res_img.paste(pr_png, (132, 627))
    del pr_png
    if Plugin_Config.SHOW_DOG_TAG:
        if result['dog_tag'] == [] or result['dog_tag'] == {}:
            pass
        else:
            res_img = dog_tag.dog_tag_2(
                img=res_img, 
                aid=aid, 
                cid=result['data']['clans'].get('clan_id',None),
                server=server, 
                response=result['dog_tag']
            )
    text_list.append(
        Text_Data(
            xy=(132+result['data']['pr']['avg_pr_text'], 690),
            text=result['data']['pr']['avg_pr_des'],
            fill=(255, 255, 255),
            font_index=1,
            font_size=35
        )
    )
    str_pr = '{:,}'.format(result['data']['pr']['avg_pr'])
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(str_pr, fontStyle)
    text_list.append(
        Text_Data(
            xy=(2284-w, 642),
            text=str_pr,
            fill=(255, 255, 255),
            font_index=1,
            font_size=80
        )
    )
    index = result['data']['pr']['battle_type'].upper()
    x0 = 324
    y0 = 860
    temp_data = result['data']['pr']
    battles_count = temp_data['battles_count']
    avg_win = temp_data['win_rate']
    avg_damage = temp_data['avg_damage']
    avg_frag = temp_data['avg_frags']
    avg_xp = temp_data['avg_exp']
    win_rate_color = Picture.hex_to_rgb(temp_data['win_rate_color'])
    avg_damage_color = Picture.hex_to_rgb(temp_data['avg_damage_color'])
    avg_frags_color = Picture.hex_to_rgb(temp_data['avg_frags_color'])

    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(battles_count, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*0-w/2, y0),
            text=battles_count,
            fill=(0, 0, 0),
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(avg_win, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*1-w/2, y0),
            text=avg_win,
            fill=win_rate_color,
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(avg_damage, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*2-w/2, y0),
            text=avg_damage,
            fill=avg_damage_color,
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(avg_frag, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*3-w/2, y0),
            text=avg_frag,
            fill=avg_frags_color,
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(avg_xp, fontStyle)
    text_list.append(
        Text_Data(
            xy=(x0+446*4-w/2, y0),
            text=avg_xp,
            fill=(0, 0, 0),
            font_index=1,
            font_size=80
        )
    )
    fontStyle = fonts.data[1][45]
    start_time = time_zone.get_str_time(result['data']['time']['start_time'],result['data']['time']['time_zone'])
    end_time = time_zone.get_str_time(result['data']['time']['end_time'],result['data']['time']['time_zone'])
    timezone = f"(UTC+{str(result['data']['time']['time_zone'])})" if result['data']['time']['time_zone'] >= 0 else f"(UTC{str(result['data']['time']['time_zone'])})"
    if lang == 'cn':
        time_str = f'数据统计区间:  {start_time} ~ {end_time}  {timezone}'
    elif lang == 'en':
        time_str = f'Time interval:  {start_time} ~ {end_time}  {timezone}'
    elif lang == 'ja':
        time_str = f'統計区間です:  {start_time} ~ {end_time}  {timezone}'
    w = Picture.x_coord(time_str, fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, 1035),
            text=time_str,
            fill=(100,100,100),
            font_index=1,
            font_size=45
        )
    )
    i = 0
    fontStyle = fonts.data[1][55]
    if battle_type in ['pvp','pvp_solo', 'pvp_div2', 'pvp_div3']:
        battle_type_list = ['pvp_solo', 'pvp_div2', 'pvp_div3']
    else:
        battle_type_list = ['rank_solo']
    for index in battle_type_list:
        x0 = 0
        y0 = 1339
        temp_data = result['data']['battle_type'][index]
        battles_count = temp_data['battles_count']
        avg_win = temp_data['win_rate']
        avg_damage = temp_data['avg_damage']
        avg_frag = temp_data['avg_frags']
        avg_xp = temp_data['avg_exp']
        win_rate_color = Picture.hex_to_rgb(temp_data['win_rate_color'])
        avg_damage_color = Picture.hex_to_rgb(temp_data['avg_damage_color'])
        avg_frags_color = Picture.hex_to_rgb(temp_data['avg_frags_color'])
        avg_pr_color = Picture.hex_to_rgb(temp_data['avg_pr_color'])
        if temp_data['avg_pr_des'] == '-':
            str_pr = '-'
        else:
            if lang == 'cn':
                str_pr = temp_data['avg_pr_des'] + '(+'+str(temp_data['avg_pr_dis'])+')'
            elif lang == 'en':
                str_pr = '■ '+str(int(temp_data['avg_pr']))
            elif lang == 'ja':
                str_pr = '■ '+str(int(temp_data['avg_pr']))
        w = Picture.x_coord(battles_count, fontStyle)
        text_list.append(
            Text_Data(
                xy=(588-w/2+x0, y0+90*i),
                text=battles_count,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(str_pr, fontStyle)
        text_list.append(
            Text_Data(
                xy=(955-w/2+x0, y0+90*i),
                text=str_pr,
                fill=avg_pr_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_win, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1307-w/2+x0, y0+90*i),
                text=avg_win,
                fill=win_rate_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_damage, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1613-w/2+x0, y0+90*i),
                text=avg_damage,
                fill=avg_damage_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_frag, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1909-w/2+x0, y0+90*i),
                text=avg_frag,
                fill=avg_frags_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_xp, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2177-w/2+x0, y0+90*i),
                text=avg_xp,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        i += 1
    i = 0
    x0 = 0
    y0 = 1844
    ship_preview_data = Game_Data.load_ship_preview_data(lang)
    ship_preview_jpg_path = os.path.join(plugin_path,'png',f'ship_preview',f'ship_preview_{lang}.png')
    ship_preview_jpg = Image.open(ship_preview_jpg_path)
    for ship_data in result['data']['ships']:
        fontStyle = fonts.data[1][50]
        ship_index = ship_data['ship_info']['ship_index']
        ship_preview_num = ship_preview_data.get(ship_index,None)
        if ship_preview_num != None:
            x = (ship_preview_num % 10)
            y = int(ship_preview_num / 10)
            ship_png = ship_preview_jpg.crop(
                ((0+360*x), (0+80*y), (360+360*x), (80+80*y)))
            res_img.alpha_composite(ship_png, (97, y0-10+90*i))
        else:
            # ★ 查无预览格时显示中文名（2026-10-16）：本地代号映射优先，其次 API 船名，最后代号
            _disp_name = ship_index
            try:
                from ..common.ship_code_name import code_cn_name
                _disp_name = (code_cn_name(ship_index)
                              or str(ship_data['ship_info'].get('ship_name') or '').strip()
                              or ship_index)
            except Exception:
                pass
            w = Picture.x_coord(_disp_name, fontStyle)
            text_list.append(
                Text_Data(
                    xy=(285-w/2+x0, y0+90*i+4),
                    text=_disp_name,
                    fill=(0, 0, 0),
                    font_index=1,
                    font_size=50
                )
            )
        temp_data = ship_data['ship_data']
        if temp_data == {}:
            continue
        battles_count = temp_data['battles_count']
        avg_win = temp_data['win_rate']
        avg_damage = temp_data['avg_damage']
        avg_frag = temp_data['avg_frags']
        avg_xp = temp_data['avg_exp']
        survival_rate = temp_data['survival_rate']
        hit_ratio = temp_data['hit_ratio']
        win_rate_color = Picture.hex_to_rgb(temp_data['win_rate_color'])
        avg_damage_color = Picture.hex_to_rgb(temp_data['avg_damage_color'])
        avg_frags_color = Picture.hex_to_rgb(temp_data['avg_frags_color'])
        avg_pr_color = Picture.hex_to_rgb(temp_data['avg_pr_color'])
        if temp_data['avg_pr_des'] == '-':
            str_pr = '-'
        else:
            if lang == 'cn':
                str_pr = temp_data['avg_pr_des'] + '(+'+str(temp_data['avg_pr_dis'])+')'
            elif lang == 'en':
                str_pr = '■ '+str(int(temp_data['avg_pr']))
            elif lang == 'ja':
                str_pr = '■ '+str(int(temp_data['avg_pr']))
        w = Picture.x_coord(battles_count, fontStyle)
        text_list.append(
            Text_Data(
                xy=(550-w/2+x0, y0+90*i+4),
                text=battles_count,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(str_pr, fontStyle)
        text_list.append(
            Text_Data(
                xy=(834-w/2+x0, y0+90*i+4),
                text=str_pr,
                fill=avg_pr_color,
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_win, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1160-w/2+x0, y0+90*i+4),
                text=avg_win,
                fill=win_rate_color,
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_damage, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1395-w/2+x0, y0+90*i+4),
                text=avg_damage,
                fill=avg_damage_color,
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_frag, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1595-w/2+x0, y0+90*i+4),
                text=avg_frag,
                fill=avg_frags_color,
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(avg_xp, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1769-w/2+x0, y0+90*i+4),
                text=avg_xp,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(survival_rate, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1978-w/2+x0, y0+90*i+4),
                text=survival_rate,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(hit_ratio, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2208-w/2+x0, y0+90*i+4),
                text=hit_ratio,
                fill=(0, 0, 0),
                font_index=1,
                font_size=50
            )
        )
        i += 1
    del ship_preview_jpg
    png_len = 1834 + 90*i + 180
    gray_png = Image.open(os.path.join(plugin_path,'png','list','gray.png'))
    res_img.alpha_composite(gray_png, (97,png_len-100))
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, png_len-140),
            text=Plugin_Config.BOT_INFO[lang],
            fill=(174, 174, 174),
            font_index=1,
            font_size=80
        )
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    res_img = res_img.crop((0, 0, 2428, png_len))
    res_img_size = res_img.size
    res_img = res_img.resize(
        (
            int(res_img_size[0]*0.5), 
            int(res_img_size[1]*0.5)
        )
    )
    return res_img


            


