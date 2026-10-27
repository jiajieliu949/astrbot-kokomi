# -*- coding: utf-8 -*-
"""候选列表渲染入口（薄转发到 common/name_list）。

name_list 在 common/ 下、不是 scripts 脚本，loader.call() 只够得着 scripts/，
故加此转发层。参数与 name_list.get_data 完全一致：[lang, ships, pic_num]。
"""
from ..common import name_list


async def get_data(
    parameter: list,
) -> dict:
    return await name_list.get_data(parameter)
