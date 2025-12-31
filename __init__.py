from .impact.util_nodes import GeneralReversedSwitch
from .byte_plus_v2 import CxBytePlus2ImageV2
from .byte_plus_v2 import CxBytePlus2VideoV2
from .load_image_by_url import LoadImageByUrl

NODE_CLASS_MAPPINGS = {
    "LoadImageByUrl": LoadImageByUrl,
    "GeneralReversedSwitch": GeneralReversedSwitch,
    "CxBytePlus2Image": CxBytePlus2ImageV2,
    "CxBytePlus2Video": CxBytePlus2VideoV2,
}
