from .utils import any_typ, is_execution_model_version_supported
import logging


class GeneralReversedSwitch:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "select": ("INT", {"default": 1, "min": 1, "max": 999999, "step": 1,
                                   "tooltip": "The output number you want to send from the input"}),
                "input": (any_typ, {"tooltip": "Any input. When connected, one more input slot is added."}),
            },
        }

    RETURN_TYPES = (any_typ, any_typ, any_typ, any_typ, any_typ, any_typ, any_typ, any_typ)
    RETURN_NAMES = ("output1", "output2", "output3", "output4", "output5", "output6", "output7", "output8")
    OUTPUT_TOOLTIPS = (
        "Output occurs only from the output selected by the 'select' value.\nWhen slots are connected, additional slots are created.",)
    FUNCTION = "doit"
    CATEGORY = "cx/GeneralReversedSwitch"

    def doit(self, select, input, **kwargs):
        if is_execution_model_version_supported():
            from comfy_execution.graph import ExecutionBlocker
        else:
            logging.warning(
                "[Impact Pack] InversedSwitch: ComfyUI is outdated. The 'select_on_execution' mode cannot function properly.")

        res = []
        cnt = 8
        for i in range(0, cnt):
            if select == i + 1:
                res.append(input)
            elif is_execution_model_version_supported():
                res.append(ExecutionBlocker(None))
            else:
                res.append(None)

        return res
