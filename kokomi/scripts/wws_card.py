import os
import time
import gc
from PIL import Image
from .. import (
    Plugin_Config,
    Picture,
    time_zone,
    Text_Data,
    Box_Data,
    call_api,
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
    # [aid server lang user_pr use_ac ac pic_num]
    try:
        path = '/b/card-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
            'lang':parameter[2],
            'use_pr':parameter[3],
            'use_ac': parameter[4],
            'ac': parameter[5]
        }
        if parameter[4] is False:
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
            lang=parameter[2],
            pic_num=parameter[6]
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
    lang: str,
    pic_num: int
) -> str:
    text_list = []
    box_list = []
    res_img = Image.open(os.path.join(plugin_path, 'png', f'bg_{lang}', 'background', 'wws_card.png'))
    fontStyle = fonts.data[1][30]
    if result['data']['clans']['clan_tag'] == 'None':
        tag = '[]'
    else:
        tag = '['+str(result['data']['clans']['clan_tag'])+']'
    tag_color = Picture.hex_to_rgb(result['data']['clans']['clan_color'])
    text_list.append(
        Text_Data(
            xy=(362, 57),
            text=tag,
            fill=tag_color,
            font_index=1,
            font_size=30
        )
    )
    w = Picture.x_coord(tag, fontStyle)
    text_list.append(
        Text_Data(
            xy=(362+w+10, 57),
            text=result['nickname'],
            fill=(255,255,255),
            font_index=1,
            font_size=30
        )
    )
    fontStyle = fonts.data[2][40]
    w = Picture.x_coord(result['data']['data']['battles_count'], fontStyle)
    text_list.append(
        Text_Data(
            xy=(436-w/2, 183),
            text=result['data']['data']['battles_count'],
            fill=(255,255,255),
            font_index=2,
            font_size=40
        )
    )
    w = Picture.x_coord(result['data']['data']['win_rate'], fontStyle)
    text_list.append(
        Text_Data(
            xy=(643-w/2, 183),
            text=result['data']['data']['win_rate'],
            fill=Picture.hex_to_rgb(result['data']['data']['win_rate_color']),
            font_index=2,
            font_size=40
        )
    )
    w = Picture.x_coord(result['data']['data']['avg_damage'], fontStyle)
    text_list.append(
        Text_Data(
            xy=(843-w/2, 183),
            text=result['data']['data']['avg_damage'],
            fill=Picture.hex_to_rgb(result['data']['data']['avg_damage_color']),
            font_index=2,
            font_size=40
        )
    )
    fontStyle = fonts.data[1][25]
    battle_time = time_zone.get_str_time_2(result['data']['data']['last_battle_time'])
    w = Picture.x_coord(battle_time, fontStyle)
    text_list.append(
        Text_Data(
            xy=(938-w, 292),
            text=battle_time,
            fill=(255,255,255),
            font_index=1,
            font_size=25
        )
    )
    play_time = result['data']['data']['play_time']['h'] + '  ' + result['data']['data']['play_time']['m'] + '  ' + result['data']['data']['play_time']['s']
    w = Picture.x_coord(play_time, fontStyle)
    text_list.append(
        Text_Data(
            xy=(938-w, 370),
            text=play_time,
            fill=(255,228,145),
            font_index=1,
            font_size=25
        )
    )
    fontStyle = fonts.data[1][15]
    token_time = 'Token有效期：' + str(int((result['data']['token']['expires_at'] - time.time())/(24*60*60))) + '天'
    text_list.append(
        Text_Data(
            xy=(364, 435),
            text=token_time,
            fill=(174, 174, 174),
            font_index=1,
            font_size=15
        )
    )
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(938-w, 435),
            text=Plugin_Config.BOT_INFO[lang],
            fill=(174, 174, 174),
            font_index=1,
            font_size=15
        )
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    return res_img