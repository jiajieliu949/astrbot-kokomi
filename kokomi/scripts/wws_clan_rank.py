import os
import gc
from PIL import Image
from .. import (
    Plugin_Config,
    Picture,
    Text_Data,
    Game_Data,
    Box_Data,
    call_api,
    clan_tag,
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
    # [clan_id ship_id server lang pic]
    try:
        path = '/b/clan-rank-data/'
        params = {
            'server': parameter[2],
            'clan_id': parameter[0],
            'ship_id': parameter[1],
            'lang': parameter[3]
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
            clan_id=parameter[0],
            server=parameter[2],
            lang=parameter[3],
            pic_num=parameter[4]
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
    clan_id: str,
    server: str,
    lang: str,
    pic_num: int
) -> str:
    text_list = []
    box_list = []
    bg_png_dict = {
        3: 'background_2',
        4: 'background_3'
    }
    list_png_dict = {
        3: 'list_2',
        4: 'list_3'
    }
    bg_png = bg_png_dict.get(pic_num,'background')
    list_png = list_png_dict.get(pic_num,'list')
    res_img_path = os.path.join(plugin_path, 'png', f'bg_{lang}', bg_png, 'wws_clanrank.png')
    bg_img = Image.open(res_img_path)
    list_png_len = int(result['data']['data_num'] / 50) + 1
    list_img_path = os.path.join(plugin_path, 'png', 'list', list_png, '60_50.png')
    list_img = Image.open(list_img_path)
    res_img = Image.new(
        mode='RGBA',
        size=(2428,1065+3500*list_png_len),
        color='white'
    )
    res_img.paste(bg_img, (0, 0))
    for i in range(list_png_len):
        res_img.paste(list_img, (0, 1065+3500*i))
    del list_img
    text_list.append(
        Text_Data(
            xy=(172, 161),
            text=str(result['data']['clan_info']['tag']),
            fill=(0, 0, 0),
            font_index=1,
            font_size=100
        )
    )
    text_list.append(
        Text_Data(
            xy=(199, 275),
            text=f'{server.upper()} -- {clan_id}',
            fill=(163, 163, 163),
            font_index=1,
            font_size=45
        )
    )
    fontStyle = fonts.data[1][55]
    if lang == 'cn':
        text_1 = '工会简介:'
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
        w = Picture.x_coord(str(result['data']['clan_info']['name']), fontStyle)
        clan_name = Picture.formate_str(
            in_str = str(result['data']['clan_info']['name']),
            str_len = w,
            max_len = 1500
        )
        text_list.append(
            Text_Data(
                xy=(169+w_1+30, 355),
                text=clan_name,
                fill=(0,0,0),
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
        text_list.append(
            Text_Data(
                xy=(169+w_2+30, 445),
                text=result['data']['clan_info']['created_at'][:10],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    elif lang == 'en':
        text_1 = 'Name:'
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
                xy=(169+w_1+30, 355),
                text=str(result['data']['clan_info']['name']),
                fill=(0,0,0),
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
        text_list.append(
            Text_Data(
                xy=(169+w_2+30, 445),
                text=result['data']['clan_info']['created_at'][:10],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    res_img, text_list = clan_tag.clan_tag_3(res_img,clan_id,text_list)
    ship_name = result['data']['ship_info']['ship_name']
    ship_tier = result['data']['ship_info']['ship_tier']
    ship_index = result['data']['ship_info']['ship_index']
    ship_nation = result['data']['ship_info']['ship_nation']
    ship_type = result['data']['ship_info']['ship_type']
    premium = result['data']['ship_info']['premium']
    special = result['data']['ship_info']['special']

    ship_name_str = Game_Data.tier_dict[ship_tier] + '    ' + ship_name
    nation_png_path = os.path.join(plugin_path,'png','nation','small',f'flag_{ship_index}.png')
    if os.path.exists(nation_png_path) is False:
        nation_png_path = os.path.join(plugin_path,'png','nation','small',f'flag_{ship_nation}.png')
    if premium:
        type_png_path = os.path.join(plugin_path,'png','ship_icon',f'{ship_type}_Premium.png')
    elif special:
        type_png_path = os.path.join(plugin_path,'png','ship_icon',f'{ship_type}_Special.png')
    else:
        type_png_path = os.path.join(plugin_path,'png','ship_icon',f'{ship_type}_Elite.png')

    fontStyle = fonts.data[1][70]
    w = Picture.x_coord(ship_name_str, fontStyle)
    all_len = 180+140+w
    text_list.append(
        Text_Data(
            xy=(all_len/2+1214-w, 602),
            text=ship_name_str,
            fill=(0,0,0),
            font_index=1,
            font_size=70
        )
    )
    nation_png = Image.open(nation_png_path)
    nation_png = nation_png.resize((108,108))
    x1 = int(1214-all_len/2)
    y1 = 580
    res_img.alpha_composite(nation_png,(x1,y1))
    del nation_png
    type_png = Image.open(type_png_path)
    x1 = int(1214-all_len/2+180)
    y1 = 593
    res_img.alpha_composite(type_png,(x1,y1))
    del type_png
    i = 0
    fontStyle = fonts.data[1][35]
    for temp_data in result['data']['members']:
        w = Picture.x_coord(str(i+1)+'.',fontStyle)
        text_list.append(
            Text_Data(
                xy=(203-w, 937+70*i),
                text=str(i+1)+'.',
                fill=(0, 0, 0),
                font_index=1,
                font_size=35
            )
        )
        text_list.append(
            Text_Data(
                xy=(213, 937+70*i),
                text=temp_data['nickname'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['battles_count'],fontStyle)
        text_list.append(
            Text_Data(
                xy=(766-w/2, 937+70*i),
                text=temp_data['battles_count'],
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        str_pr = '■ '+str(int(temp_data['avg_pr']))
        w = Picture.x_coord(str_pr, fontStyle)
        text_list.append(
            Text_Data(
                xy=(973-w/2, 937+70*i),
                text=str_pr,
                fill=Picture.hex_to_rgb(temp_data['avg_pr_color']),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['win_rate'],fontStyle)
        text_list.append(
            Text_Data(
                xy=(1184-w/2, 937+70*i),
                text=temp_data['win_rate'],
                fill=Picture.hex_to_rgb(temp_data['win_rate_color']),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['avg_damage'],fontStyle)
        text_list.append(
            Text_Data(
                xy=(1384-w/2, 937+70*i),
                text=temp_data['avg_damage'],
                fill=Picture.hex_to_rgb(temp_data['avg_damage_color']),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['avg_frags'],fontStyle)
        text_list.append(
            Text_Data(
                xy=(1573-w/2, 937+70*i),
                text=temp_data['avg_frags'],
                fill=Picture.hex_to_rgb(temp_data['avg_frags_color']),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(str(temp_data['max_damage']),fontStyle)
        text_list.append(
            Text_Data(
                xy=(1751-w/2, 937+70*i),
                text=str(temp_data['max_damage']),
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(str(temp_data['max_exp']),fontStyle)
        text_list.append(
            Text_Data(
                xy=(1958-w/2, 937+70*i),
                text=str(temp_data['max_exp']),
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(str(temp_data['cache_update_time'])+' 天前',fontStyle)
        text_list.append(
            Text_Data(
                xy=(2170-w/2, 937+70*i),
                text=str(temp_data['cache_update_time'])+' 天前',
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        i += 1
    png_len = 924 + 70*i + 140
    gray_png = Image.open(os.path.join(plugin_path,'png','list','gray.png'))
    res_img.alpha_composite(gray_png, (97,png_len-80))
    fontStyle = fonts.data[1][80]
    w = Picture.x_coord(Plugin_Config.BOT_INFO[lang], fontStyle)
    text_list.append(
        Text_Data(
            xy=(1214-w/2, png_len-110),
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