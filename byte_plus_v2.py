from byteplussdkarkruntime import Ark
from byteplussdkarkruntime.types.images import SequentialImageGenerationOptions
from comfy_api_nodes.apinode_utils import (
    bytesio_to_image_tensor,
    download_url_to_video_output,
    tensor_to_data_uri,
)
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
import base64
import torch
import time
import os

ratio_list = [0.33, 0.35, 0.38, 0.4, 0.42, 0.47, 0.51, 0.55, 0.56, 0.6, 0.63, 0.66, 0.67, 0.7, 0.72, 0.75, 0.78, 0.82,
              0.85, 0.88, 0.91, 0.94, 0.97, 1, 1.06, 1.1, 1.17, 1.24, 1.29, 1.33, 1.42, 1.46, 1.5, 1.56, 1.62, 1.67,
              1.74, 1.82, 1.78, 1.86, 1.95, 2, 2.05, 2.1, 2.2, 2.25, 2.3, 2.35, 2.4, 2.53, 2.67, 2.82, 3]

ratio_for_image = {
    "1:1": "2048x2048",
    "4:3": "2304x1728",
    "3:4": "1728x2304",
    "16:9": "2560x1440",
    "9:16": "1440x2560",
    "3:2": "2496x1664",
    "2:3": "1664x2496",
    "21:9": "3024x1296",
}


def get_aspect_ratio(width, height):
    ratio = round(width / height, 2)
    if ratio == 1:
        return "1:1"
    elif ratio == 0.67:
        return "2:3"
    elif ratio == 1.5:
        return "3:2"
    elif ratio == 0.75:
        return "3:4"
    elif ratio == 1.33:
        return "4:3"
    elif ratio == 0.56:
        return "9:16"
    elif ratio == 1.78:
        return "16:9"
    elif ratio == 2.33:
        return "21:9"
    return "1:1"


class CxBytePlus2VideoV2:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "optional": {
                "image": ("IMAGE",),
            },
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "What you wish to see in the output image."
                    },
                ),
                "model": ("STRING",),
                "width": (
                    "INT",
                    {
                        "default": 512,
                    },
                ),
                "height": (
                    "INT",
                    {
                        "default": 512,
                    },
                ),
                "frame_rate": (
                    "INT",
                    {
                        "default": 20,
                    },
                ),
                "length": (
                    "INT",
                    {
                        "default": 61,
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": -1,
                    },
                ),
            }
        }

    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "save_video"
    OUTPUT_NODE = True
    CATEGORY = "cx/CxBytePlus2Video"

    async def save_video(self, model: str, prompt: str, width: int, height: int, seed: int,
                         frame_rate: int, length: int, image: torch.Tensor = None):
        seed = seed % 2147483647
        client = Ark(
            base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
            api_key=os.getenv('BYTE_PLUS_API_KEY'),
        )
        duration = int(length / frame_rate)
        ratio = "16:9"
        if width == 1664:
            ratio = "4:3"
        elif width == 1440:
            ratio = "1:1"
        elif width == 1248:
            ratio = "3:4"
        elif width == 1088:
            ratio = "9:16"
        elif width == 2176:
            ratio = "21:9"
        extra_params = f" --duration {duration} --seed {seed} --ratio {ratio}"
        if image is not None:
            image_str = tensor_to_data_uri(image)
            create_result = client.content_generation.tasks.create(
                model="ep-20250902181440-jk422",
                content=[
                    {
                        "type": "text",
                        "text": prompt + extra_params,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_str
                        }
                    }
                ]
            )
        else:
            create_result = client.content_generation.tasks.create(
                model="ep-20250902181440-jk422",
                content=[
                    {
                        "type": "text",
                        "text": prompt + extra_params,
                    }
                ]
            )

        # Polling query section
        print("----- polling task status -----")
        task_id = create_result.id
        video_url = ""
        while True:
            get_result = client.content_generation.tasks.get(task_id=task_id)
            status = get_result.status
            if status == "succeeded":
                print("----- task succeeded -----")
                print(get_result)
                video_url = get_result.content.video_url
                break
            elif status == "failed":
                print("----- task failed -----")
                print(f"Error: {get_result.error}")
                return
            else:
                print(f"Current status: {status}, Retrying after 1 seconds...")
                time.sleep(1)

        return (await download_url_to_video_output(video_url),)


class CxBytePlus2ImageV2:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "optional": {
                "image": ("IMAGE",),
            },
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "What you wish to see in the output image."
                    },
                ),
                "model": ("STRING",),
                "width": (
                    "INT",
                    {
                        "default": 512,
                    },
                ),
                "height": (
                    "INT",
                    {
                        "default": 512,
                    },
                ),
                "cfg_scale": (
                    "FLOAT",
                    {
                        "default": 2.5,
                        "min": 1,
                        "max": 10,
                    },
                ),
                "batch_size": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 10,
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": -1,
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "save_image"
    OUTPUT_NODE = True
    CATEGORY = "cx/CxBytePlus2Image"

    def save_image(self, model: str, prompt: str, width: int, height: int, cfg_scale: float, seed: int,
                   batch_size: int, image: torch.Tensor = None):
        seed = seed % 2147483647
        client = Ark(
            base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
            api_key=os.getenv('BYTE_PLUS_API_KEY'),
        )
        ratio = get_aspect_ratio(width, height)
        size = "2048x2048"
        if ratio in ratio_for_image:
            size = ratio_for_image[ratio]
        if image is not None:
            image = tensor_to_data_uri(image)
        options = SequentialImageGenerationOptions()
        options.max_images = batch_size
        images_response = client.images.generate(
            model="ep-20250918155819-q7k8b",
            seed=seed,
            prompt=prompt,
            size=size,
            image=image,
            response_format="b64_json",
            watermark=False,
            sequential_image_generation="auto",
            sequential_image_generation_options=options
        )

        returned_list = []
        for image in images_response.data:
            response_api = image.b64_json
            image_data = base64.b64decode(response_api)
            returned_image = bytesio_to_image_tensor(BytesIO(image_data))
            returned_list.append(returned_image)
        return (torch.cat(returned_list),)
