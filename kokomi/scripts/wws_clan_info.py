import os
import gc
from PIL import Image
from .. import (
    Plugin_Config,
    Picture,
    Text_Data,
    Box_Data,
    clan_tag,
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
    # [clan_id server lang pic]
    try:
        path = '/b/clan-basic-data/'
        params = {
            'server': parameter[1],
            'clan_id':parameter[0],
            'lang':parameter[2]
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
            server=parameter[1],
            lang=parameter[2],
            pic_num=parameter[3]
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
    res_img_path = os.path.join(plugin_path, 'png', f'bg_{lang}', bg_png, 'wws_clan.png')
    bg_img = Image.open(res_img_path)
    list_png_len = int(len(result['data']['members']) / 50) + 1
    list_img_path = os.path.join(plugin_path, 'png', 'list', list_png, '60_50.png')
    list_img = Image.open(list_img_path)
    res_img = Image.new(
        mode='RGBA',
        size=(2428,2338+3500*list_png_len),
        color='white'
    )
    res_img.paste(bg_img, (0, 0))
    for i in range(list_png_len):
        res_img.paste(list_img, (0, 2338+3500*i))
    del list_img
    text_list.append(
        Text_Data(
            xy=(172, 161),
            text=str(result['data']['info']['tag']),
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
        w = Picture.x_coord(str(result['data']['info']['name']), fontStyle)
        clan_name = Picture.formate_str(
            in_str = str(result['data']['info']['name']),
            str_len = w,
            max_len = 1000
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
                text=result['data']['info']['created_at'][:10],
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
                text=str(result['data']['info']['name']),
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
                text=result['data']['info']['created_at'][:10],
                fill=(0,0,0),
                font_index=1,
                font_size=55
            )
        )
    if Plugin_Config.SHOW_CLAN_TAG is True:
        res_img, text_list = clan_tag.clan_tag_1(res_img,clan_id,text_list,result['data']['cvc_data'])
    if result['data']['achievements'] == {} or result['data']['achievements']['4'] == 0:
        pass
    else:
        min_id = 4
        for ach_id, ach_num in result['data']['achievements'].items():
            ach_id = int(ach_id)
            if ach_num == 0:
                continue
            if ach_id < min_id:
                min_id = ach_id
            text_list.append(
                Text_Data(
                    xy=(338+220*(4-ach_id), 1662),
                    text=f'x{ach_num}',
                    fill=(0,0,0),
                    font_index=1,
                    font_size=45
                )
            )
        cw_png_path = os.path.join(plugin_path, 'png', f'cw', '{}.png'.format(min_id))
        cw_png = Image.open(cw_png_path)
        x1 = 97
        y1 = 1560
        res_img.alpha_composite(cw_png, (x1,y1))
        del cw_png
    fontStyle = fonts.data[1][80]
    clan_user = '{}/{}'.format(
        result['data']['info']['members_count'],
        result['data']['info']['max_members_count']
    )
    w = Picture.x_coord(clan_user,fontStyle)
    text_list.append(
        Text_Data(
            xy=(1216-w/2, 1934),
            text=clan_user,
            fill=(0,0,0),
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(result['data']['statistics']['battles_count'],fontStyle)
    text_list.append(
        Text_Data(
            xy=(413-w/2, 1934),
            text=result['data']['statistics']['battles_count'],
            fill=(0,0,0),
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(result['data']['statistics']['win_rate'],fontStyle)
    text_list.append(
        Text_Data(
            xy=(813-w/2, 1934),
            text=result['data']['statistics']['win_rate'],
            fill=(0,0,0),
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(result['data']['statistics']['avg_damage'],fontStyle)
    text_list.append(
        Text_Data(
            xy=(1613-w/2, 1934),
            text=result['data']['statistics']['avg_damage'],
            fill=(0,0,0),
            font_index=1,
            font_size=80
        )
    )
    w = Picture.x_coord(result['data']['statistics']['avg_exp'],fontStyle)
    text_list.append(
        Text_Data(
            xy=(2013-w/2, 1934),
            text=result['data']['statistics']['avg_exp'],
            fill=(0,0,0),
            font_index=1,
            font_size=80
        )
    )
    i = 0
    for index in ['dry_dock','shipbuilding_factory','superships_home','coal_yard','steel_yard','paragon_yard','university','design_department','academy']:
        build_data = result['data']['buildings'][index]
        x = int(i/3)
        y = int(i%3)
        if lang == 'cn':
            level = '{} / {} 级'.format(
                build_data['level'],
                build_data['max_level']
            )
            text_list.append(
                Text_Data(
                    xy=(310 + 754*x, 775 + 199*y),
                    text=level,
                    fill=(0,0,0),
                    font_index=1,
                    font_size=55
                )
            )
        elif lang == 'en':
            level = '{}  out of  {}'.format(
                build_data['level'],
                build_data['max_level']
            )
            text_list.append(
                Text_Data(
                    xy=(310 + 754*x, 775 + 199*y),
                    text=level,
                    fill=(0,0,0),
                    font_index=1,
                    font_size=55
                )
            )
        if build_data['level'] != 0:
            if index == 'superships_home':
                if build_data['level_data'] != []:
                    j = 0
                    for s_build_data in build_data['level_data']:
                        building1 = s_build_data[0]
                        building2 = s_build_data[1]
                        text_list.append(
                            Text_Data(
                                xy=(220 + 754*x, 852 + 199*y + 40*j),
                                text=building1,
                                fill=(47,200,148),
                                font_index=1,
                                font_size=25
                            )
                        )
                        text_list.append(
                            Text_Data(
                                xy=(295 + 754*x, 852 + 199*y + 40*j),
                                text=building2,
                                fill=(127,127,127),
                                font_index=1,
                                font_size=25
                            )
                        ) 
                        j += 1
            else:
                if build_data['level_data'] != None: 
                    building1 = build_data['level_data'][0]
                    building2 = build_data['level_data'][1]
                    text_list.append(
                        Text_Data(
                            xy=(220 + 754*x, 852 + 199*y),
                            text=building1,
                            fill=(47,200,148),
                            font_index=1,
                            font_size=25
                        )
                    )
                    text_list.append(
                        Text_Data(
                            xy=(295 + 754*x, 852 + 199*y),
                            text=building2,
                            fill=(127,127,127),
                            font_index=1,
                            font_size=25
                        )
                    )
        i += 1
    role_dict = {
        '指挥官': 0,
        '副指挥官': 1,
        '征募官': 2,
        '现役军官': 3,
        '前线军官': 4,
        '军校见习生': 5,
        'Commander': 0,
        'Deputy Commander': 1,
        'Recruiter': 2,
        'Commissioned Officer': 3,
        'Line Officer': 4,
        'Midshipman': 5
    }
    clan_role_png_path = os.path.join(plugin_path,'png',f'bg_{lang}',f'clan_role.png')
    clan_role_png = Image.open(clan_role_png_path)
    i = 0
    fontStyle = fonts.data[1][35]
    for temp_data in result['data']['members']:
        role_id = role_dict.get(temp_data['role'],5)
        ship_png = clan_role_png.crop(((0), (0+60*role_id), (250), (60+60*role_id)))
        res_img.alpha_composite(ship_png, (139, 2198 +70*i))
        text_list.append(
            Text_Data(
                xy=(403, 2210+70*i),
                text=temp_data['nickname'],
                fill=(0, 0, 0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['battles_count'],fontStyle)
        text_list.append(
            Text_Data(
                xy=(956-w/2, 2210+70*i),
                text=temp_data['battles_count'],
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['win_rate'],fontStyle)
        text_list.append(
            Text_Data(
                xy=(1156-w/2, 2210+70*i),
                text=temp_data['win_rate'],
                fill=Picture.hex_to_rgb(temp_data['win_rate_color']),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['avg_exp'],fontStyle)
        text_list.append(
            Text_Data(
                xy=(1356-w/2, 2210+70*i),
                text=temp_data['avg_exp'],
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['avg_damage'],fontStyle)
        text_list.append(
            Text_Data(
                xy=(1555-w/2, 2210+70*i),
                text=temp_data['avg_damage'],
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(temp_data['avg_frags'],fontStyle)
        text_list.append(
            Text_Data(
                xy=(1763-w/2, 2210+70*i),
                text=temp_data['avg_frags'],
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(str(temp_data['days_in_clan']),fontStyle)
        text_list.append(
            Text_Data(
                xy=(1959-w/2, 2210+70*i),
                text=str(temp_data['days_in_clan']),
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        w = Picture.x_coord(str(temp_data['last_battle_time']),fontStyle)
        text_list.append(
            Text_Data(
                xy=(2165-w/2, 2210+70*i),
                text=str(temp_data['last_battle_time']),
                fill=(0,0,0),
                font_index=1,
                font_size=35
            )
        )
        i += 1
    del clan_role_png
    png_len = 2198 + 70*i + 140
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