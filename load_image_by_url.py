# copy from: https://github.com/talesofai/comfyui-browser/blob/main/nodes/load_image_by_url.py
import hashlib
import os
import io

import requests
from PIL import Image, ImageSequence, ImageOps
from pillow_heif import register_heif_opener
from PIL.GifImagePlugin import GifImageFile
from PIL.MpoImagePlugin import MpoImageFile
from PIL.PngImagePlugin import PngImageFile
from PIL.WebPImagePlugin import WebPImageFile
from requests.adapters import HTTPAdapter, Retry


import numpy as np
import torch

import folder_paths

from urllib.parse import urlparse

register_heif_opener()

# Allow loading large images without DecompressionBombError
Image.MAX_IMAGE_PIXELS = None

ANIMATE_IMAGE_TYPES = (GifImageFile, PngImageFile, WebPImageFile)

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def get_default_headers(url: str, media_type: str = "image") -> dict:
    parsed_url = urlparse(url)
    # Removed manual "Host" header injection to prevent HTTP/2 :authority conflicts
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if media_type == "image":
        headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    else:
        headers["Accept"] = "*/*"
    return headers


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
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ["STRING", {}],
            },
            "optional": {
                "cache": ["BOOLEAN", {"default": True}],
            },
        }

    def __init__(self):
        self.url: str = ""

    @property
    def filepath(self):
        input_dir = folder_paths.get_input_directory()
        return os.path.join(input_dir, hashlib.md5(self.url.encode()).hexdigest()[:48] + '.jpg')

    def download_by_url(self, cache: bool):
        headers = get_default_headers(self.url, media_type="image")
        
        try:
            resp = http_client().get(self.url, headers=headers, timeout=(30, 60))
            if resp.status_code != 200:
                raise ValueError(
                    f"Failed to load image from {self.url}: {resp.status_code}, {resp.text}")
            content = resp.content
        except requests.exceptions.RequestException as e:
            print(f"[LoadImageByUrl] requests failed with {e}, falling back to urllib.request (HTTP/1.1)...")
            import urllib.request
            req = urllib.request.Request(self.url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as fallback_resp:
                    if fallback_resp.status != 200:
                        raise ValueError(f"Failed to load image from {self.url}: {fallback_resp.status}")
                    content = fallback_resp.read()
            except Exception as fallback_e:
                raise ValueError(f"Failed to download image from {self.url} via urllib: {fallback_e} (initial requests error: {e})")

        if cache:
            temp_path = self.filepath + ".tmp"
            try:
                with open(temp_path, 'wb') as file:
                    file.write(content)
                os.replace(temp_path, self.filepath)
            except Exception as e:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                print(f"[LoadImageByUrl] Warning: Failed to write cache file: {e}")

        return content

    def run(self, url: str, cache: bool = True):
        self.url = url
        image_path = self.filepath

        img = None
        if cache and os.path.isfile(image_path):
            try:
                img = Image.open(image_path)
                img.verify()
                img = Image.open(image_path)
            except Exception as e:
                print(f"[LoadImageByUrl] Cached file corrupted, re-downloading: {e}")
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception:
                        pass
                img = None

        if img is None:
            content = self.download_by_url(cache)
            img = Image.open(io.BytesIO(content))

        # handle truncated or invalid MPO image
        if isinstance(img, MpoImageFile):
            frames = getattr(img, 'n_frames', 1)
            for n in reversed(range(frames)):
                try:
                    img.seek(n)
                    if n < frames - 1:
                        img.n_frames = n + 1
                        img.is_animated = img.n_frames > 1
                        print(f"[LoadImageByUrl] Truncated MPO image detected, change n_frames({frames}) => {n + 1}")
                    break
                except Exception as e:
                    print(f"[LoadImageByUrl] MPO seek frame {n} error: {e}")
                    continue

            try:
                img.seek(0)
            except Exception as e:
                print(f"[LoadImageByUrl] MPO seek(0) error: {e}, fallback to single frame")
                img.n_frames = 1
                img.is_animated = False

        first_image: Image.Image | None = None
        output_images: list[torch.Tensor] = []
        try:
            for i in ImageSequence.Iterator(img):
                try:
                    i = ImageOps.exif_transpose(i)
                except Exception as e:
                    print(f"[LoadImageByUrl] Error while exif_transpose: {e}")

                i = i.convert("RGB")
                if first_image and i.size != first_image.size:
                    print(f"[LoadImageByUrl] Image size mismatch first image size: {i.size} != {first_image.size}")
                    continue

                if output_images and isinstance(img, ANIMATE_IMAGE_TYPES):
                    image_type = str(type(img)).split(".")[-1].split("ImageFile")[0].lower()
                    print(f'[LoadImageByUrl] Only take the first frame of <{image_type}> image, total: {img.n_frames}')
                    break

                if first_image is None:
                    first_image = i

                image = np.array(i).astype(np.float32) / 255.0
                image = torch.from_numpy(image)[None,]
                output_images.append(image)
        except Exception as e:
            print(f"[LoadImageByUrl] Warning during frame iteration: {e}")
            if not output_images:
                raise e

        if not output_images:
            raise RuntimeError(f"[LoadImageByUrl] Could not load any valid frames from {url}")

        output_image = None
        if len(output_images) > 1:
            try:
                output_image = torch.cat(output_images, dim=0)
            except Exception as e:
                print(f"[LoadImageByUrl] Error while concatenating images: {e}")

        if output_image is None:
            output_image = output_images[0]

        return (output_image, )

