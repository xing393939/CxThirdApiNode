import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import torch

from PIL import Image

def log(message:str, message_type:str='info'):
    name = 'LayerStyle'

    if message_type == 'error':
        message = '\033[1;41m' + message + '\033[m'
    elif message_type == 'warning':
        message = '\033[1;31m' + message + '\033[m'
    elif message_type == 'finish':
        message = '\033[1;32m' + message + '\033[m'
    else:
        message = '\033[1;33m' + message + '\033[m'
    print(f"# 😺dzNodes: {name} -> {message}")

def tensor2pil(t_image: torch.Tensor)  -> Image:
    return Image.fromarray(np.clip(255.0 * t_image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def pil2tensor(image:Image) -> torch.Tensor:
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)


def image2mask(image:Image) -> torch.Tensor:
    if image.mode == 'L':
        return torch.tensor([pil2tensor(image)[0, :, :].tolist()])
    else:
        image = image.convert('RGB').split()[0]
        return torch.tensor([pil2tensor(image)[0, :, :].tolist()])


# 向上取整数倍
def num_round_up_to_multiple(number: int, multiple: int) -> int:
    remainder = number % multiple
    if remainder == 0:
        return number
    else:
        factor = (number + multiple - 1) // multiple  # 向上取整的计算方式
        return factor * multiple


def fit_resize_image(image:Image, target_width:int, target_height:int, fit:str, resize_sampler:str, background_color:str = '#000000') -> Image:
    image = image.convert('RGB')
    orig_width, orig_height = image.size
    if image is not None:
        if fit == 'letterbox':
            if orig_width / orig_height > target_width / target_height:  # 更宽，上下留黑
                fit_width = target_width
                fit_height = int(target_width / orig_width * orig_height)
            else:  # 更瘦，左右留黑
                fit_height = target_height
                fit_width = int(target_height / orig_height * orig_width)
            fit_image = image.resize((fit_width, fit_height), resize_sampler)
            ret_image = Image.new('RGB', size=(target_width, target_height), color=background_color)
            ret_image.paste(fit_image, box=((target_width - fit_width)//2, (target_height - fit_height)//2))
        elif fit == 'crop':
            if orig_width / orig_height > target_width / target_height:  # 更宽，裁左右
                fit_width = int(orig_height * target_width / target_height)
                fit_image = image.crop(
                    ((orig_width - fit_width)//2, 0, (orig_width - fit_width)//2 + fit_width, orig_height))
            else:   # 更瘦，裁上下
                fit_height = int(orig_width * target_height / target_width)
                fit_image = image.crop(
                    (0, (orig_height-fit_height)//2, orig_width, (orig_height-fit_height)//2 + fit_height))
            ret_image = fit_image.resize((target_width, target_height), resize_sampler)
        else:
            ret_image = image.resize((target_width, target_height), resize_sampler)
    return  ret_image


'''Value Functions'''
def is_valid_mask(tensor:torch.Tensor) -> bool:
    return not bool(torch.all(tensor == 0).item())