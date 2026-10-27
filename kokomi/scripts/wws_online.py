import os
import gc
from PIL import Image
from .. import (
    Plugin_Config,
    Picture,
    Text_Data,
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
    # [lang pic]
    try:
        path = '/p/online-player/'
        params = {
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
            lang=parameter[0],
            pic_num=parameter[1]
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
    bg_png_dict = {
        2: 'background_1',
        3: 'background_2',
        4: 'background_3'
    }
    bg_png = bg_png_dict.get(pic_num,'background')
    res_img_path = os.path.join(plugin_path, 'png', f'bg_{lang}', bg_png, 'wws_online.png')
    res_img = Image.open(res_img_path)
    all_user = '{:,}'.format(result['data']['all']['online_players']).replace(',', ' ')
    text_list.append(
        Text_Data(
            xy=(187, 265),
            text=all_user,
            fill=(70,70,70),
            font_index=2,
            font_size=65
        )
    )
    i = 0
    fontStyle = fonts.data[2][65]
    for index in ['asia','eu','na','ru','cn']:
        online_player = '{:,}'.format(result['data'][index]['online_players']).replace(',', ' ')
        server_time = result['data'][index]['server_time']
        w = Picture.x_coord(server_time, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1040-w, 445+176*i),
                text=server_time,
                fill=(90,90,90),
                font_index=2,
                font_size=65
            )
        )
        w = Picture.x_coord(online_player, fontStyle)
        text_list.append(
            Text_Data(
                xy=(1370-w, 445+176*i),
                text=online_player,
                fill=(70,70,70),
                font_index=2,
                font_size=65
            )
        )
        i += 1
    fontStyle = fonts.data[1][55]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(760-w/2, 1280),
            text=Plugin_Config.BOT_INFO[lang],
            fill=(174, 174, 174),
            font_index=1,
            font_size=55
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


            


