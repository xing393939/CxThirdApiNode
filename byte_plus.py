from byteplussdkarkruntime import Ark
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

ratio_list = [0.33,0.35,0.38,0.4,0.42,0.47,0.51,0.55,0.56,0.6,0.63,0.66,0.67,0.7,0.72,0.75,0.78,0.82,0.85,0.88,0.91,0.94,0.97,1,1.06,1.1,1.17,1.24,1.29,1.33,1.42,1.46,1.5,1.56,1.62,1.67,1.74,1.82,1.78,1.86,1.95,2,2.05,2.1,2.2,2.25,2.3,2.35,2.4,2.53,2.67,2.82,3]

class CxBytePlus2Video:
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


class CxBytePlus2Image:
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

    def multi_generate(self, batch_size, **kwargs):
        client = Ark(
            base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
            api_key=os.getenv('BYTE_PLUS_API_KEY'),
        )
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i in range(batch_size):
                if i != 0 and "seed" in kwargs:
                    del kwargs["seed"]
                futures.append(executor.submit(client.images.generate, **kwargs))
            results = []
            for future in as_completed(futures):
                results.append(future.result())
            return results

    def save_image(self, model: str, prompt: str, width: int, height: int, cfg_scale: float, seed: int,
                   batch_size: int, image: torch.Tensor = None):
        seed = seed % 2147483647
        size="{}x{}".format(width, height)
        print(f"size: {size}")
        if image is not None:
            size = width / height
            radio = 0.33
            for v in ratio_list:
                radio = v
                if size < v:
                    break
            image_str = tensor_to_data_uri(image)
            kwargs = {
                "model": "ep-20250902181354-4b59s",
                "response_format": "b64_json",
                "image": image_str,
                "seed": seed,
                "size": 'adaptive',
                "watermark": False,
                "prompt": prompt
            }
            multi_response = self.multi_generate(batch_size, **kwargs)
        else:
            kwargs = {
                "model": "ep-20250902181150-lxn82",
                "response_format": "b64_json",
                "size": size,
                "seed": seed,
                "watermark": False,
                "prompt": prompt
            }
            multi_response = self.multi_generate(batch_size, **kwargs)
        returned_list = []
        for images_response in multi_response:
            response_api = images_response.data[0].b64_json
            image_data = base64.b64decode(response_api)
            returned_image = bytesio_to_image_tensor(BytesIO(image_data))
            returned_list.append(returned_image)
        return (torch.cat(returned_list),)
