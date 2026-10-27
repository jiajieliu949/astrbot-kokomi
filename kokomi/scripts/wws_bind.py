import os
import gc
from PIL import Image
from .. import (
    Plugin_Config,
    Picture,
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
    # [aid server lang platform user_id user_pr pic]
    try:
        path = '/b/user-data/'
        params = {
            'aid': parameter[0],
            'server': parameter[1],
        }
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
            use_pr=parameter[5],
            lang=parameter[2],
            platform=parameter[3],
            platform_id=parameter[4],
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
    aid: str,
    server: str,
    use_pr: bool,
    lang: str,
    platform: str,
    platform_id: str,
    pic_num: int
) -> str:
    text_list = []
    box_list = []
    bg_png_dict = {
        2: 'background_1',
        3: 'background_2',
        4: 'background_3'
    }
    bg_png = bg_png_dict.get(pic_num,'background')
    res_img_path = os.path.join(plugin_path, 'png', f'bg_{lang}', bg_png, 'wws_bind.png')
    res_img = Image.open(res_img_path)
    fontStyle = fonts.data[1][55]
    w = Picture.x_coord(platform.upper(), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 415),
            text=platform.upper(),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(platform_id, fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 560),
            text=platform_id,
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    if lang == 'cn':
        lang_info = '简体中文'
        w = Picture.x_coord(lang_info, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 705),
                text=lang_info,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        lang_info = 'English'
        w = Picture.x_coord(lang_info, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 705),
                text=lang_info,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'ja':
        lang_info = '日本語'
        w = Picture.x_coord(lang_info, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 705),
                text=lang_info,
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    
    w = Picture.x_coord(str(aid), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1104),
            text=str(aid),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(server.upper(), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1249),
            text=server.upper(),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    nickname = result['data']['user']['nickname']
    w = Picture.x_coord(' ' if nickname is None else str(nickname), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1394),
            text=' ' if nickname is None else str(nickname),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['user']['query_times']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1539),
            text=str(result['data']['user']['query_times']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['user']['cache_update_time']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 1684),
            text=str(result['data']['user']['cache_update_time']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['recent']['class']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 2083),
            text=str(result['data']['recent']['class']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['recent']['data_num']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 2228),
            text=str(result['data']['recent']['data_num']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    w = Picture.x_coord(str(result['data']['recent']['start_date']), fontStyle)
    text_list.append(
        Text_Data(
            xy=(1750-w, 2373),
            text=str(result['data']['recent']['start_date']),
            fill=(0,0,0),
            font_index=1,
            font_size=55
        )
    )
    if lang == 'cn':
        recents_class = {
            0:'-',
            1:'官方接口-1',
            2:'官方接口-2'
        }
        w = Picture.x_coord(recents_class[result['data']['recents']['class']], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 2772),
                text=recents_class[result['data']['recents']['class']],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        recents_class = {
            0:'-',
            1:'Official API-1',
            2:'Official API-2'
        }
        w = Picture.x_coord(recents_class[result['data']['recents']['class']], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 2772),
                text=recents_class[result['data']['recents']['class']],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'ja':
        recents_class = {
            0:'-',
            1:'Official API-1',
            2:'Official API-2'
        }
        w = Picture.x_coord(recents_class[result['data']['recents']['class']], fontStyle)
        text_list.append(
            Text_Data(
                xy=(1750-w, 2772),
                text=recents_class[result['data']['recents']['class']],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    on_png_path = os.path.join(plugin_path, 'png', 'list', 'on.png')
    on_png = Image.open(on_png_path)
    off_png_path = os.path.join(plugin_path, 'png', 'list', 'off.png')
    off_png = Image.open(off_png_path)
    if use_pr == True:
        x1 = 1430
        y1 = 817
        res_img.alpha_composite(on_png, (x1,y1))
    else:
        x1 = 1430
        y1 = 817
        res_img.alpha_composite(off_png, (x1,y1))
    if result['data']['recent']['enable'] == True:
        x1 = 1430
        y1 = 1905
        res_img.alpha_composite(on_png, (x1,y1))
    else:
        x1 = 1430
        y1 = 1905
        res_img.alpha_composite(off_png, (x1,y1))
    if result['data']['recents']['enable'] == True:
        x1 = 1430
        y1 = 2594
        res_img.alpha_composite(on_png, (x1,y1))
    else:
        x1 = 1430
        y1 = 2594
        res_img.alpha_composite(off_png, (x1,y1))
    del on_png
    del off_png
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(950-w/2, 2890),
            text=Plugin_Config.BOT_INFO[lang],
            fill=(174, 174, 174),
            font_index=1,
            font_size=80
        )
    )
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    res_img_size = res_img.size
    res_img = res_img.resize(
        (
            int(res_img_size[0]*0.5), 
            int(res_img_size[1]*0.5)
        )
    )
    return res_img


            


