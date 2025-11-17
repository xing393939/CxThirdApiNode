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

    def filename(self):
        return hashlib.md5(self.url.encode()).hexdigest()[:48] + '.jpg'

    def download_by_url(self):
        input_dir = folder_paths.get_input_directory()
        res = http_client().get(self.url)
        if res.status_code == 200:
            download_path = os.path.join(input_dir, self.filename())
            with open(download_path, 'wb') as file:
                file.write(res.content)
            return res.content
        else:
            raise ValueError(f"Failed to load image from {self.url}: {res.status_code} {res.text}")

    def run(self, url: str, cache: bool = True):
        self.url = url
        input_dir = folder_paths.get_input_directory()
        image_path = os.path.join(input_dir, self.filename())
        if not cache or not os.path.isfile(image_path):
            img = Image.open(io.BytesIO(self.download_by_url()))
        else:
            img = Image.open(image_path)

        # handle truncated MPO image
        if isinstance(img, MpoImageFile):
            for frame in reversed(range(n_frames := img.n_frames)):
                try:
                    img.seek(frame)
                    if frame < n_frames - 1:
                        img.n_frames = frame + 1
                        img.is_animated = img.n_frames > 1
                        print(
                            f"Truncated MPO image detected, change n_frames({n_frames}) => {img.n_frames}")
                    break
                except ValueError:
                    continue
            img.seek(0)

        output_images = []
        for i in ImageSequence.Iterator(img):
            i = ImageOps.exif_transpose(i)
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
            output_images.append(image)

        if len(output_images) > 1:
            output_image = torch.cat(output_images, dim=0)
        else:
            output_image = output_images[0]

        return (output_image, )
