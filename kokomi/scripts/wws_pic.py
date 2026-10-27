import gc
from .. import (
    write_error,
    change_pic
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
    # [platform user_id pic_num]
    try:
        change_pic(
            id=parameter[1],
            pic_num=parameter[2]
        )
        res = {
            'status': 'ok',
            'message': 'CHANGE SUCCESSED'
        }
        gc.collect()
        return res
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