import os
import time
from PIL import Image
from .. import (
    Plugin_Config,
    Picture,
    Text_Data
)
from .. import plugin_path
def main(
    result:dict, 
    lang: str,
    pic_num: int
) -> dict:
    if result['message'] in ['NETWORK FAILURE','NETWORK TIMEOUT']:
        error_type = 'network_error'
        error_data = [
            time.strftime("%Y-%m-%d %H:%M:%S UTC+8", time.localtime(time.time())),
            result['error'],
            'None',
            Plugin_Config.VERSON
        ]
    else:
        error_type = 'program_error'
        error_data = [
            time.strftime("%Y-%m-%d %H:%M:%S UTC+8", time.localtime(time.time())),
            result['error'],
            result['track_id'],
            Plugin_Config.VERSON
        ]
    func_dict = {
        'cn': get_png_cn,
        'en': get_png_en,
        'ja': get_png_ja
    }
    func = func_dict[lang]
    res_img = func(
        error_type=error_type,
        error_data=error_data,
        pic_num=pic_num
    )
    result = {
        'status': 'ok', 
        'message': 'SUCCESS', 
        'img': None
    }
    result['img'] = Picture.return_img(img=res_img)['img']

    return result

def get_png_ja(
    error_type:str,
    error_data:list,
    pic_num:int
):
    text_list = []
    bg_png_dict = {
        2: 'background_1'
    }
    bg_png = bg_png_dict.get(pic_num,'background')
    png_path = os.path.join(plugin_path, 'png', 'bg_ja', bg_png, f'kokomi_{error_type}.png')
    res_img = Image.open(png_path)
    text_list.append(
        Text_Data(
            xy=(815, 820),
            text=error_data[0],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    text_list.append(
        Text_Data(
            xy=(930, 876),
            text=error_data[1],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    text_list.append(
        Text_Data(
            xy=(891, 930),
            text=error_data[2],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    text_list.append(
        Text_Data(
            xy=(1010, 985),
            text=error_data[3],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    res_img = Picture.add_text(text_list, res_img)
    res_img_size = res_img.size
    res_img = res_img.resize(
        (
            int(res_img_size[0]*0.5), 
            int(res_img_size[1]*0.5)
        )
    )
    return res_img

def get_png_en(
    error_type:str,
    error_data:list,
    pic_num:int
):
    text_list = []
    bg_png_dict = {
        2: 'background_1'
    }
    bg_png = bg_png_dict.get(pic_num,'background')
    png_path = os.path.join(plugin_path, 'png', 'bg_en', bg_png, f'kokomi_{error_type}.png')
    res_img = Image.open(png_path)
    text_list.append(
        Text_Data(
            xy=(815, 820),
            text=error_data[0],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    text_list.append(
        Text_Data(
            xy=(930, 876),
            text=error_data[1],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    text_list.append(
        Text_Data(
            xy=(891, 930),
            text=error_data[2],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    text_list.append(
        Text_Data(
            xy=(1010, 985),
            text=error_data[3],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    res_img = Picture.add_text(text_list, res_img)
    res_img_size = res_img.size
    res_img = res_img.resize(
        (
            int(res_img_size[0]*0.5), 
            int(res_img_size[1]*0.5)
        )
    )
    return res_img

def get_png_cn(
    error_type:str,
    error_data:list,
    pic_num:int
):
    text_list = []
    bg_png_dict = {
        2: 'background_1'
    }
    bg_png = bg_png_dict.get(pic_num,'background')
    png_path = os.path.join(plugin_path, 'png', 'bg_cn', bg_png, f'kokomi_{error_type}.png')
    res_img = Image.open(png_path)
    text_list.append(
        Text_Data(
            xy=(797, 820),
            text=error_data[0],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    text_list.append(
        Text_Data(
            xy=(890, 876),
            text=error_data[1],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    text_list.append(
        Text_Data(
            xy=(890, 930),
            text=error_data[2],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    text_list.append(
        Text_Data(
            xy=(890, 985),
            text=error_data[3],
            fill=(75,75,75),
            font_index=1,
            font_size=45
        )
    )
    res_img = Picture.add_text(text_list, res_img)
    res_img_size = res_img.size
    res_img = res_img.resize(
        (
            int(res_img_size[0]*0.5), 
            int(res_img_size[1]*0.5)
        )
    )
    return res_img