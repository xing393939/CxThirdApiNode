# author: Trung0246 --->
class TautologyStr(str):
    def __ne__(self, other):
        return False

def is_execution_model_version_supported():
    try:
        import comfy_execution  # noqa: F401
        return True
    except Exception:
        return False

class ByPassTypeTuple(tuple):
    def __getitem__(self, index):
        if index > 0:
            index = 0
        item = super().__getitem__(index)
        if isinstance(item, str):
            return TautologyStr(item)
        return item


# wildcard trick is taken from pythongossss's
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

any_typ = AnyType("*")
