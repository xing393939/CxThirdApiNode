def is_execution_model_version_supported():
    try:
        import comfy_execution  # noqa: F401
        return True
    except Exception:
        return False

# wildcard trick is taken from pythongossss's
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

any_typ = AnyType("*")
