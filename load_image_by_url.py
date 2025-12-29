# copy from: https://github.com/talesofai/comfyui-browser/blob/main/nodes/load_image_by_url.py
import hashlib
import os
import io

import requests
from PIL.MpoImagePlugin import MpoImageFile
from PIL import Image, ImageSequence, ImageOps
from pillow_heif import register_heif_opener
from requests.adapters import HTTPAdapter, Retry

import numpy as np
import torch

import folder_paths

register_heif_opener()


def http_client():
    adapter = HTTPAdapter(max_retries=Retry(3, backoff_factor=0.1))
    http = requests.session()
    http.mount('http://', adapter)
    http.mount('https://', adapter)

    return http


class LoadImageByUrl:
    CATEGORY = "cx/LoadImageByUrl"

    RETURN_TYPES = ("IMAGE", )
    RETURN_NAMES = ("IMAGE", )

    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "url": ["STRING", {}],
            },
            "optional": {
                "cache": ["BOOLEAN", {"default": True}],
            },
        }

    def __init__(self):
        self.url = ""

    @property
    def filepath(self):
        input_dir = folder_paths.get_input_directory()
        return os.path.join(input_dir, hashlib.md5(self.url.encode()).hexdigest()[:48] + '.jpg')

    def download_by_url(self, cache: bool):
        resp = http_client().get(self.url, timeout=(30, 30))
        if resp.status_code != 200:
            raise ValueError(
                f"Failed to load image from {self.url}: {resp.status_code}, {resp.text}")

        if cache:
            with open(self.filepath, 'wb') as file:
                file.write(resp.content)

        return resp.content

    def run(self, url: str, cache: bool = True):
        self.url = url
        image_path = self.filepath
        if not cache or not os.path.isfile(image_path):
            img = Image.open(io.BytesIO(self.download_by_url(cache)))
        else:
            img = Image.open(image_path)

        # handle truncated MPO image
        if isinstance(img, MpoImageFile):
            for n in reversed(range(frames := img.n_frames)):
                try:
                    img.seek(n)
                    if n < frames - 1:
                        img.n_frames = n + 1
                        img.is_animated = img.n_frames > 1
                        print(f"Truncated MPO image detected, change n_frames({frames}) => {n + 1}")
                    break
                except ValueError:
                    continue

            img.seek(0)

        first_image: Image.Image | None = None
        output_images: list[torch.Tensor] = []
        for i in ImageSequence.Iterator(img):
            i = ImageOps.exif_transpose(i)
            i = i.convert("RGB")
            if first_image and i.size != first_image.size:
                print(f"Image size mismatch first image size: {i.size} != {first_image.size}")
                continue

            if first_image is None:
                first_image = i

            image = np.array(i).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
            output_images.append(image)

        if len(output_images) > 1:
            output_image = torch.cat(output_images, dim=0)
        else:
            output_image = output_images[0]

        return (output_image, )
