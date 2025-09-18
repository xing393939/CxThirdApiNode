from .byte_plus import CxBytePlus2Image
from .byte_plus import CxBytePlus2Video
from .image_scale_by_aspect_ratio_v2 import ImageScaleByAspectRatioV2

NODE_CLASS_MAPPINGS = {
    "CxBytePlus2Image": CxBytePlus2Image,
    "CxBytePlus2Video": CxBytePlus2Video,
    "LayerUtility: ImageScaleByAspectRatio V2": ImageScaleByAspectRatioV2
}