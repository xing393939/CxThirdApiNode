from .byte_plus_v2 import CxBytePlus2ImageV2
from .byte_plus_v2 import CxBytePlus2VideoV2
from .image_scale_by_aspect_ratio_v2 import ImageScaleByAspectRatioV2

NODE_CLASS_MAPPINGS = {
    "CxBytePlus2Image": CxBytePlus2ImageV2,
    "CxBytePlus2Video": CxBytePlus2VideoV2,
    "LayerUtility: ImageScaleByAspectRatio V2": ImageScaleByAspectRatioV2
}