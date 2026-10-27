import os
from PIL import Image, ImageDraw, ImageFont
import gc
from .wws_error import main as create_error_card
from .wws_message import main as return_message
from .. import (
    Plugin_Config,
    Picture,
    Game_Data,
    Text_Data,
    Box_Data,
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
    if result['status'] == 'error':
        result = create_error_card(result,parameter[0],parameter[2])
    if result['status'] == 'ok' and result['message'] == 'SUCCESS':
        return result
    else:
        lang = parameter[0]
        result = return_message(result,lang)
    return result

async def get_data(
    parameter: list,
) -> dict:
    # [lang data pic]
    try:
        try:
            _pn = int(parameter[2])
        except Exception:  # noqa: BLE001
            _pn = -1
        if _pn == 99:
            # ★ 候选图 v3 新渲染（2026-10-16 用户定稿，no_flags 卡片式设计）
            res_img = get_png_v3(result=parameter[1], lang=parameter[0])
        else:
            res_img = get_png(
                result=parameter[1],
                lang=parameter[0],
                pic_num=parameter[2]
            )
        result = {
            'status': 'ok', 
            'message': 'SUCCESS', 
            'img': None
        }
        _ri = Picture.return_img(img=res_img)
        result = (_ri if isinstance(_ri, dict)
                  else {'status': 'ok', 'message': 'SUCCESS', 'img': _ri})
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


_FONT_LADDER = (50, 45, 40, 35, 30, 25)  # load_fonts.py 预载的 1 号字体尺寸


def _fit_font_size(text, col_px: int, base: int = 50, min_size: int = 25) -> int:
    """★ 按列宽自适应字号（2026-10-16 v19）：结果吸附到字体缓存实际预载的尺寸。

    旧版会返回 34/46 这类未预载值 -> fonts.data[1] KeyError -> 候选图 PROGRAM ERROR
    （长船名必触发，如「彼得罗巴甫洛夫斯克EM」）。"""
    s = str(text or "")
    if not s:
        return base
    w = sum(1.0 if ord(c) > 0x2E80 else 0.55 for c in s)
    need = w * base
    if need <= col_px:
        return base
    size = max(min_size, int(base * col_px / need))
    for cand in _FONT_LADDER:
        if size >= cand:
            return cand
    return _FONT_LADDER[-1]


def get_png(
    result: list,
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
    bg_img = Image.open(os.path.join(plugin_path, 'png', f'bg_{lang}', bg_png, 'wws_ships_info2.png'))
    list_png_len = int(len(result) / 50) + 1
    list_img = Image.open(os.path.join(plugin_path, 'png', 'list', list_png, '80_50_2.png'))
    res_img = Image.new(
        mode='RGBA',
        size=(2428,587+4500*list_png_len),
        color='white'
    )
    res_img.paste(bg_img, (0, 0))
    for i in range(list_png_len):
        res_img.paste(list_img, (0, 587+4500*i))
    del list_img
    if bg_png == 'background':
        # ★ 表头调整（2026-10-16 v22，用户定案）：
        #   ① 主标题「您输入的船只名称匹配到了多艘船只」→ 加粗加大：55 号字 + 2px 双绘
        #      （无粗体字库，双绘偏移模拟加粗；仅盖标题两行后重绘，覆盖 y 128-272）；
        #   ② 副标题「请在20秒内选择对应的序号」保持 45 号；
        #   ③ 「序号」列表头（75 灰、50 号，列中心 x=145）。
        _d = ImageDraw.Draw(res_img)
        _bg = bg_img.convert('RGB').getpixel((300, 200))  # 标题带底色（自适应模板）
        _d.rectangle((200, 128, 1736, 272), fill=_bg)
        _f55 = fonts.data[1][55]
        _f45 = fonts.data[1][45]
        _f50 = fonts.data[1][50]
        _t1 = '您输入的船只名称匹配到了多艘船只'
        _w1 = Picture.x_coord(_t1, _f55)
        _x1 = 968 - _w1 / 2
        text_list.append(Text_Data(xy=(_x1, 136), text=_t1,
                                   fill=(75, 75, 75), font_index=1, font_size=55))
        text_list.append(Text_Data(xy=(_x1 + 2, 136), text=_t1,
                                   fill=(75, 75, 75), font_index=1, font_size=55))
        _t2 = '请在20秒内选择对应的序号'
        _w2 = Picture.x_coord(_t2, _f45)
        text_list.append(Text_Data(xy=(968 - _w2 / 2, 208), text=_t2,
                                   fill=(75, 75, 75), font_index=1, font_size=45))
        _th = '序号'
        _wh = Picture.x_coord(_th, _f50)
        text_list.append(Text_Data(xy=(145 - _wh / 2, 334), text=_th,
                                   fill=(75, 75, 75), font_index=1, font_size=50))
    i = 0
    fontStyle = fonts.data[1][50]
    for ship_data in result:
        # ★ 序号列（2026-10-16 v21）：去掉数字后多余的小数点，居中于「序号」表头（列中心 x=145）
        _num = f"{i+1}"
        text_list.append(
            Text_Data(
                xy=(145 - Picture.x_coord(_num, fontStyle) / 2, 417+90*i),
                text=_num,
                fill=(0,0,0),
                font_index=1,
                font_size=50
            )
        )
        ship_tier = Game_Data.tier_dict[ship_data['ship_data']['tier']]
        ship_type = ship_data['ship_data']['type']
        w = Picture.x_coord(ship_tier,fontStyle)
        text_list.append(
            Text_Data(
                xy=(280-w/2, 417+90*i),
                text=ship_tier,
                fill=(0,0,0),
                font_index=1,
                font_size=50
            )
        )
        w = Picture.x_coord(ship_type,fontStyle)
        text_list.append(
            Text_Data(
                xy=(504-w/2, 417+90*i),
                text=ship_type,
                fill=(0,0,0),
                font_index=1,
                font_size=50
            )
        )
        if lang == 'cn':
            text_list.append(
                Text_Data(
                    xy=(743, 417+90*i),
                    text=ship_data['ship_data']['cn'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=_fit_font_size(ship_data['ship_data']['cn'], 470)
                )
            )
            text_list.append(
                Text_Data(
                    xy=(1238, 417+90*i),
                    text=ship_data['ship_data']['en'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=_fit_font_size(ship_data['ship_data']['en'], 640)
                )
            )
        elif lang == 'en':
            text_list.append(
                Text_Data(
                    xy=(743, 417+90*i),
                    text=ship_data['ship_data']['en'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=_fit_font_size(ship_data['ship_data']['en'], 640)
                )
            )
            text_list.append(
                Text_Data(
                    xy=(1238, 417+90*i),
                    text='-',
                    fill=(0,0,0),
                    font_index=1,
                    font_size=50
                )
            )
        elif lang == 'ja':
            text_list.append(
                Text_Data(
                    xy=(743, 417+90*i),
                    text=ship_data['ship_data']['ja'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=_fit_font_size(ship_data['ship_data']['ja'], 470)
                )
            )
            text_list.append(
                Text_Data(
                    xy=(1238, 417+90*i),
                    text=ship_data['ship_data']['en'],
                    fill=(0,0,0),
                    font_index=1,
                    font_size=_fit_font_size(ship_data['ship_data']['en'], 640)
                )
            )
        i += 1

    png_len = 407 + 90*i + 90
    # gray_png = Image.open(os.path.join(plugin_path,'png','list','gray_2.png'))
    # res_img.alpha_composite(gray_png, (97,png_len-100))
    res_img = Picture.add_box(box_list, res_img)
    res_img = Picture.add_text(text_list, res_img)
    res_img = res_img.crop((0, 0, 1936, png_len))
    res_img_size = res_img.size
    res_img = res_img.resize(
        (
            int(res_img_size[0]*0.5), 
            int(res_img_size[1]*0.5)
        )
    )
    return res_img


# ============================================================
# 候选图 v3（2026-10-16 用户定稿）：no_flags 卡片式设计
#   * 浅蓝卡片 + 圆角 + 六边形等级徽章（真月桂枝蒙版染色）+ 序号圆
#   * 列头小图标（盾牌/轮船/清单/地球，程序化绘制）
#   * 逐列居中：序号圆/徽章/类型组/中英文
#   由 main.py 以 pic=99 触发；其余 pic 值走上面的旧渲染，互不影响。
# ============================================================
import math as _math

_V3_CACHE = {}
_V3_HEADER_BG = "#E4F1FF"
_V3_COL_BG = "#E8F3FF"
_V3_ROW_HL_BG = "#F0F7FF"
_V3_ROW_BG = "#FFFFFF"
_V3_ROW_BORDER = "#E3EDF8"
_V3_SEP = "#D9E7F8"
_V3_NAVY = "#102F59"
_V3_SUB = "#527397"
_V3_LBL = "#496B91"
_V3_ICON_NAVY = "#2F5C8C"
_V3_ICO = "#3D5F8D"
_V3_CIRC_NUM1 = "#5DA4F7"
_V3_CIRC_NUM = "#91A9C9"
_V3_TIER_COLORS = {1: "#8D99AE", 2: "#A3C64C", 3: "#6FAF46", 4: "#3E8948",
                   5: "#17A398", 6: "#2E9BD6", 7: "#1A6FBE", 8: "#9829B2",
                   9: "#641E8C", 10: "#D6A11A", 11: "#D93B3B"}
_V3_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII",
             8: "VIII", 9: "IX", 10: "X", 11: "★"}
_V3_COL_CENTERS = {1: 137, 2: 380, 3: 695, 4: 1128, 5: 1638}
# 类型中文化（2026-10-16 v3.6）：UI 全中文，类型列不再显示英文
_V3_TYPE_CN = {"Cruiser": "巡洋舰", "Battleship": "战列舰", "Destroyer": "驱逐舰",
               "Submarine": "潜艇", "AirCarrier": "航母"}


def _v3_font(size):
    key = ("font", size)
    if key not in _V3_CACHE:
        _V3_CACHE[key] = ImageFont.truetype(
            os.path.join(plugin_path, "fonts", "SHSCN.ttf"), size)
    return _V3_CACHE[key]


def _v3_asset(name):
    key = ("asset", name)
    if key not in _V3_CACHE:
        _V3_CACHE[key] = Image.open(
            os.path.join(plugin_path, "png", "pick_v3", name)).convert("RGBA")
    return _V3_CACHE[key]


def _v3_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _v3_lighten(h, t):
    r, g, b = _v3_rgb(h)
    return (int(r + (255 - r) * t), int(g + (255 - g) * t), int(b + (255 - b) * t))


def _v3_t_bold(d, xy, s, size, fill, anchor="mm"):
    d.text(xy, s, font=_v3_font(size), fill=fill, anchor=anchor)
    d.text((xy[0] + 2, xy[1]), s, font=_v3_font(size), fill=fill, anchor=anchor)


def _v3_t_norm(d, xy, s, size, fill, anchor="mm"):
    d.text(xy, s, font=_v3_font(size), fill=fill, anchor=anchor)


def _v3_fit(d, s, maxw, sizes=(30, 25, 22)):
    for sz in sizes:
        try:
            if d.textlength(str(s), font=_v3_font(sz)) <= maxw:
                return sz
        except Exception:  # noqa: BLE001
            return sizes[-1]
    return sizes[-1]


def _v3_wreath(color, mirror=False):
    src = _v3_asset("wreath_left.png")
    img = Image.new("RGBA", src.size, _v3_rgb(color) + (0,))
    img.putalpha(src.split()[3])
    if mirror:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    # v3.6：月桂等比放大 1.2 倍，与加大后的字号匹配
    img = img.resize((int(img.width * 1.2), int(img.height * 1.2)), Image.LANCZOS)
    return img


def _v3_badge(im, cx, cy, tier):
    tc = _V3_TIER_COLORS.get(tier, "#9E9E9E")
    d = ImageDraw.Draw(im)
    hw, hh = 34, 39

    def _hex(cxx, cyy, w, h):
        return [(cxx, cyy - h / 2), (cxx + w / 2, cyy - h / 4), (cxx + w / 2, cyy + h / 4),
                (cxx, cyy + h / 2), (cxx - w / 2, cyy + h / 4), (cxx - w / 2, cyy - h / 4)]

    d.polygon(_hex(cx, cy, hw * 2, hh * 2), fill=_v3_lighten(tc, 0.35))
    d.polygon(_hex(cx, cy - 1, hw * 2 - 8, hh * 2 - 8), fill=_v3_rgb(tc))
    wl = _v3_wreath(tc, mirror=False)
    wr = _v3_wreath(tc, mirror=True)
    im.paste(wl, (int(cx - 34 - wl.width + 1), int(cy - wl.height / 2)), wl)
    im.paste(wr, (int(cx + 34 - 1), int(cy - wr.height / 2)), wr)
    _v3_t_bold(d, (cx, cy), _V3_ROMAN.get(tier, "?"), 32, "#FFFFFF")


def _v3_icon_shield(im, cx, cy):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((cx - 19, cy - 21, cx + 19, cy + 8), radius=9, fill=_V3_ICO)
    d.polygon([(cx - 19, cy + 2), (cx + 19, cy + 2), (cx, cy + 22)], fill=_V3_ICO)
    _v3_t_bold(d, (cx, cy - 6), "U", 28, "#FFFFFF")


def _v3_icon_boat(im, cx, cy):
    d = ImageDraw.Draw(im)
    c = _V3_ICO
    d.polygon([(cx - 24, cy + 12), (cx - 17, cy + 2), (cx + 14, cy + 2),
               (cx + 24, cy + 8), (cx + 14, cy + 14), (cx - 17, cy + 14)], fill=c)
    d.rectangle((cx - 8, cy - 12, cx + 10, cy + 2), fill=c)
    d.rectangle((cx - 2, cy - 21, cx + 6, cy - 12), fill=c)
    d.rectangle((cx - 16, cy - 5, cx - 9, cy + 2), fill=c)


def _v3_icon_list(im, cx, cy):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((cx - 19, cy - 20, cx + 19, cy + 20), radius=10, fill=_V3_ICO)
    d.rounded_rectangle((cx - 12, cy - 12, cx + 12, cy - 6), radius=2, fill="#FFFFFF")
    d.rounded_rectangle((cx - 12, cy - 2, cx + 12, cy + 4), radius=2, fill="#FFFFFF")
    d.rounded_rectangle((cx - 12, cy + 8, cx + 6, cy + 14), radius=2, fill="#FFFFFF")


def _v3_icon_globe(im, cx, cy):
    d = ImageDraw.Draw(im)
    c = _V3_ICO
    R = 20
    d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=c, width=3)
    d.ellipse((cx - 9, cy - R + 1, cx + 9, cy + R - 1), outline=c, width=3)
    for dy, w in ((0, 3), (-10, 2), (10, 2)):
        half = _math.sqrt(max(R * R - dy * dy, 0)) - 2
        d.line((cx - half, cy + dy, cx + half, cy + dy), fill=c, width=w)


def _v3_type_icon(ship_type, h=48):
    canvas = Image.new("RGBA", (48, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    c = _V3_ICON_NAVY
    if ship_type == "Battleship":
        d.polygon([(2, 30), (8, 20), (40, 20), (46, 26), (40, 32), (8, 32)], fill=c)
        d.rectangle((16, 12, 30, 20), fill=c)
        d.rectangle((21, 4, 25, 12), fill=c)
        d.rectangle((10, 14, 14, 20), fill=c)
        d.rectangle((32, 14, 36, 20), fill=c)
    elif ship_type == "Destroyer":
        d.polygon([(6, 29), (12, 22), (40, 22), (45, 26), (40, 30), (12, 30)], fill=c)
        d.rectangle((19, 14, 29, 22), fill=c)
        d.rectangle((23, 8, 26, 14), fill=c)
    elif ship_type == "Submarine":
        d.ellipse((2, 18, 44, 32), fill=c)
        d.rectangle((20, 8, 27, 20), fill=c)
        d.rectangle((22, 4, 24, 8), fill=c)
    elif ship_type == "AirCarrier":
        d.polygon([(2, 26), (8, 21), (40, 21), (46, 21), (46, 27), (8, 27)], fill=c)
        d.rectangle((8, 14, 13, 21), fill=c)
        d.rectangle((10, 10, 12, 14), fill=c)
    else:  # Cruiser / 未知
        d.polygon([(4, 30), (10, 21), (38, 21), (44, 26), (38, 31), (10, 31)], fill=c)
        d.rectangle((17, 12, 30, 21), fill=c)
        d.rectangle((22, 5, 26, 12), fill=c)
        d.rectangle((11, 15, 15, 21), fill=c)
    w = h * canvas.width // canvas.height
    return canvas.resize((w, h), Image.LANCZOS)


def get_png_v3(result, lang="cn"):
    """候选图 v3 渲染：result = ships 列表（含 ship_data）。宽 1920，高随行数自适应。"""
    rows = []
    for it in (result or []):
        sd = it.get("ship_data") or {}
        try:
            tier = int(sd.get("tier") or it.get("level") or 0)
        except Exception:  # noqa: BLE001
            tier = 0
        rows.append({
            "tier": tier,
            "type": sd.get("type") or "",
            "nation": sd.get("nation") or it.get("nation") or "",
            "ru": sd.get("ru") or "",
            "cn": sd.get("cn") or it.get("name") or "?",
            "en": sd.get("en") or sd.get("cn") or it.get("name") or "?",
        })
    n = max(len(rows), 1)
    H = 748 + (n - 3) * 124 if n >= 3 else 748 - (3 - n) * 124
    im = Image.new("RGB", (1920, H), "#FFFFFF")
    d = ImageDraw.Draw(im)

    # 表头卡片（v3.6：船图标与标题成组整体居中）
    d.rounded_rectangle((30, 28, 1891, 191), radius=24, fill=_V3_HEADER_BG)
    ship_icon = _v3_asset("ship_icon.png")
    title = "您输入的船只名称匹配到了多艘船只"
    ttl_w = d.textlength(title, font=_v3_font(66))
    grp_w = ship_icon.width + 24 + ttl_w + 8  # 图标 + 间距 + 标题(伪粗体加2px)
    gx = 960 - grp_w / 2
    im.paste(ship_icon, (int(gx), 47), ship_icon)
    _v3_t_bold(d, (int(gx + ship_icon.width + 24 + ttl_w / 2), 82), title, 66, _V3_NAVY)
    _v3_t_norm(d, (960, 148), "请在20秒内选择对应的序号", 54, _V3_SUB)

    # 列头带 + 分隔线 + 图标列头（逐列居中）
    d.rounded_rectangle((30, 218, 1891, 296), radius=16, fill=_V3_COL_BG)
    for x in (240, 520, 870, 1385):
        d.line((x, 226, x, 288), fill=_V3_SEP, width=2)
    _v3_t_norm(d, (_V3_COL_CENTERS[1], 258), "序号", 48, _V3_LBL)
    tw = d.textlength("等级", font=_v3_font(48))
    left = _V3_COL_CENTERS[2] - (42 + 12 + tw) / 2
    _v3_icon_shield(im, left + 21, 258)
    _v3_t_norm(d, (left + 54, 258), "等级", 48, _V3_LBL, anchor="lm")
    tw = d.textlength("类型", font=_v3_font(48))
    left = _V3_COL_CENTERS[3] - (52 + 10 + tw) / 2
    _v3_icon_boat(im, left + 26, 258)
    _v3_t_norm(d, (left + 62, 258), "类型", 48, _V3_LBL, anchor="lm")
    tw = d.textlength("简体中文", font=_v3_font(48))
    left = _V3_COL_CENTERS[4] - (40 + 12 + tw) / 2
    _v3_icon_list(im, left + 20, 258)
    _v3_t_norm(d, (left + 52, 258), "简体中文", 48, _V3_LBL, anchor="lm")
    tw = d.textlength("原名", font=_v3_font(48))
    left = _V3_COL_CENTERS[5] - (42 + 12 + tw) / 2
    _v3_icon_globe(im, left + 21, 258)
    _v3_t_norm(d, (left + 54, 258), "原名", 48, _V3_LBL, anchor="lm")

    # 行（v3.6：行高 113→100，去首行高亮 —— 序号圆统一色，避免「推荐第一个」的误读）
    for i, r in enumerate(rows):
        y0 = 306 + i * 124
        d.rounded_rectangle((30, y0, 1891, y0 + 100), radius=16,
                            fill=_V3_ROW_BG,
                            outline=_V3_ROW_BORDER, width=2)
        yc = y0 + 50
        # 序号圆
        d.ellipse((_V3_COL_CENTERS[1] - 33, yc - 33, _V3_COL_CENTERS[1] + 33, yc + 33),
                  fill=_V3_CIRC_NUM)
        _v3_t_bold(d, (_V3_COL_CENTERS[1], yc), str(i + 1), 54, "#FFFFFF")
        # 等级徽章
        _v3_badge(im, _V3_COL_CENTERS[2], yc, r["tier"])
        # 类型组（v3.6：类型中文化）
        type_cn = _V3_TYPE_CN.get(r["type"], r["type"])
        ic = _v3_type_icon(r["type"])
        tw = d.textlength(type_cn, font=_v3_font(46))
        left = _V3_COL_CENTERS[3] - (52 + 10 + tw) / 2
        im.paste(ic, (int(left + 26 - ic.width / 2), yc - ic.height // 2), ic)
        _v3_t_bold(d, (left + 62, yc), type_cn, 46, _V3_ICON_NAVY, anchor="lm")
        # 船名（列宽内自动缩号；中文列已加宽到 870-1385）
        _v3_t_bold(d, (_V3_COL_CENTERS[4], yc), r["cn"],
                   _v3_fit(d, r["cn"], 495, sizes=(54, 48, 42, 36)), _V3_NAVY)
        # 原名列（2026-10-16 用户定案）：俄系船显示俄语名，其余系保持英文
        disp = r["ru"] if (r.get("nation") == "Russia" and r.get("ru")) else r["en"]
        _v3_t_norm(d, (_V3_COL_CENTERS[5], yc), disp,
                   _v3_fit(d, disp, 486, sizes=(52, 46, 40, 34)), _V3_NAVY)

    del d
    gc.collect()
    return im
