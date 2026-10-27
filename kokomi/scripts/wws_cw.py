import os
import time
import gc
from PIL import Image
# from PIL.PngImagePlugin import PngImageFile
from .. import (
    Plugin_Config,
    Picture,
    Text_Data,
    Box_Data,
    call_api,
    dog_tag,
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
    # [aid server lang use_ac ac pic]
    try:
        path = '/b/cw-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
            'lang':parameter[2],
            'use_ac': parameter[3],
            'ac': parameter[4]
        }
        if parameter[3] is False:
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
            pic_num=parameter[5]
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
    res_img_path = os.path.join(plugin_path, 'png', f'bg_{lang}', bg_png, 'wws_cw.png')
    bg_img = Image.open(res_img_path)
    list_png_len = int(result['data']['data_num'] / 50) + 1
    list_img_path = os.path.join(plugin_path, 'png', 'list', list_png, '80_50.png')
    list_img = Image.open(list_img_path)
    res_img = Image.new(
        mode='RGBA',
        size=(2428,1328+4500*list_png_len),
        color='white'
    )
    res_img.paste(bg_img, (0, 0))
    for i in range(list_png_len):
        res_img.paste(list_img, (0, 1328+4500*i))
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
        text_2 = '注册时间:'
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
        creat_time = time.strftime(
            "%Y-%m-%d", 
            time.localtime(result['data']['user']['created_at'])
        )
        text_list.append(
            Text_Data(
                xy=(169+w_2+30, 448),
                text=creat_time,
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
        text_2 = 'Created at:'
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
        creat_time = time.strftime(
            "%Y-%m-%d", 
            time.localtime(result['data']['user']['created_at'])
        )
        text_list.append(
            Text_Data(
                xy=(169+w_2+30, 448),
                text=creat_time,
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
        text_2 = '登録日:'
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
        creat_time = time.strftime(
            "%Y-%m-%d", 
            time.localtime(result['data']['user']['created_at'])
        )
        text_list.append(
            Text_Data(
                xy=(169+w_2+30, 448),
                text=creat_time,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
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
    if result['data']['achievements'] == {}:
        pass
    else:
        min_id = 4
        for ach_id, ach_num in result['data']['achievements'].items():
            ach_id = int(ach_id)
            if ach_id < min_id:
                min_id = ach_id
            text_list.append(
                Text_Data(
                    xy=(338+220*(4-ach_id), 810),
                    text=f'x{ach_num}',
                    fill=(0,0,0),
                    font_index=1,
                    font_size=45
                )
            )
        cw_png_path = os.path.join(plugin_path, 'png', f'cw', '{}.png'.format(min_id))
        cw_png = Image.open(cw_png_path)
        x1 = 98
        y1 = 702
        res_img.alpha_composite(cw_png, (x1,y1))
        del cw_png
    i = 0
    for index in result['data']['season']:
        x0 = 0
        y0 = 1158
        season_number = index['cvc_season']
        if lang == 'cn':
            season_number = f'第 {season_number} 赛季'
        elif lang == 'en':
            season_number = f'Season {season_number}'
        elif lang == 'ja':
            season_number = f'第 {season_number} シーズン'
        battles_count = index['battles_count']
        avg_win = index['win_rate']
        avg_damage = index['avg_damage']
        avg_frag = index['avg_frags']
        avg_xp = index['avg_exp']
        win_rate_color = Picture.hex_to_rgb(index['win_rate_color'])
        fontStyle = fonts.data[1][55]
        w = Picture.x_coord(season_number, fontStyle)
        text_list.append(
            Text_Data(
                xy=(312-w/2+x0, y0+90*i),
                text=season_number,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(battles_count, fontStyle)
        text_list.append(
            Text_Data(
                xy=(669-w/2+x0, y0+90*i),
                text=battles_count,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_win, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1002-w/2+x0, y0+90*i),
                text=avg_win,
                fill=win_rate_color,
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_damage, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1365-w/2+x0, y0+90*i),
                text=avg_damage,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_frag, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1753-w/2+x0, y0+90*i),
                text=avg_frag,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
        w = Picture.x_coord(avg_xp, fontStyle)
        text_list.append(
            Text_Data(
                xy=(2091-w/2+x0, y0+90*i),
                text=avg_xp,
                fill=(0, 0, 0),
                font_index=1,
                font_size=55
            )
        )
        i += 1
    png_len = 1148 + 90*i + 180
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


            


