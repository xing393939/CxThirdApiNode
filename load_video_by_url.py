import os
import hashlib
import urllib.parse
import importlib

def get_vhs_load_video_class():
    # Method 1: Get from nodes registry if already loaded
    import nodes
    cls = nodes.NODE_CLASS_MAPPINGS.get("VHS_LoadVideo")
    if cls is not None:
        return cls
    
    # Method 2: Import dynamically using importlib to bypass potential hyphen (-) syntax limitations in directory names
    import_paths = [
        "custom_nodes.ComfyUI-VideoHelperSuite.videohelpersuite.nodes",
        "custom_nodes.ComfyUI_VideoHelperSuite.videohelpersuite.nodes",
        "custom_nodes.ComfyUI-VideoHelperSuite.nodes",
        "custom_nodes.ComfyUI_VideoHelperSuite.nodes",
        "videohelpersuite.nodes",
    ]
    for path in import_paths:
        try:
            module = importlib.import_module(path)
            cls = getattr(module, "VHS_LoadVideo", None)
            if cls is not None:
                return cls
        except ImportError:
            continue
            
    return None


class LoadVideoByUrl:
    CATEGORY = "cx/LoadVideoByUrl"
    
    # Standard fallback return signatures. Will be dynamically synchronized below if the class is found.
    RETURN_TYPES = ("IMAGE", "INT", "AUDIO", "VHS_VIDEOINFO")
    RETURN_NAMES = ("IMAGE", "frame_count", "AUDIO", "video_info")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        vhs_cls = get_vhs_load_video_class()
        if vhs_cls is None:
            return {
                "required": {
                    "url": ("STRING", {"default": ""}),
                },
                "optional": {
                    "cache": ("BOOLEAN", {"default": True}),
                }
            }
        
        orig_inputs = vhs_cls.INPUT_TYPES()
        inputs = {
            "required": orig_inputs.get("required", {}).copy(),
            "optional": orig_inputs.get("optional", {}).copy(),
        }
        
        if "video" in inputs["required"]:
            inputs["required"].pop("video")
        inputs["required"]["url"] = ("STRING", {"default": "", "multiline": False})
        inputs["optional"]["cache"] = ("BOOLEAN", {"default": True})
        
        return inputs

    def run(self, url: str, cache: bool = True, **kwargs):
        vhs_cls = get_vhs_load_video_class()
        if vhs_cls is None:
            raise RuntimeError("Could not locate the VHS_LoadVideo class from VideoHelperSuite. Please make sure VideoHelperSuite is installed.")
            
        import folder_paths
        input_dir = folder_paths.get_input_directory()
        if not os.path.exists(input_dir):
            os.makedirs(input_dir, exist_ok=True)
            
        parsed_url = urllib.parse.urlparse(url)
        ext = os.path.splitext(parsed_url.path)[1]
        if ext:
            # Strip query parameters or hashes from file extension
            ext = ext.split('?')[0].split('#')[0]
        # Keep original extension if valid (typically starts with . and 1-5 chars length, e.g. .mp4, .webp, .gif)
        if not ext or len(ext) > 6 or not ext.startswith('.'):
            ext = '.mp4'
            
        filename = "vhs_cache_" + hashlib.md5(url.encode()).hexdigest()[:32] + ext
        dest_path = os.path.join(input_dir, filename)
        
        if not cache or not os.path.exists(dest_path):
            print(f"[LoadVideoByUrl] Downloading video from: {url} -> {dest_path}")
            import requests
            from requests.adapters import HTTPAdapter
            from requests.packages.urllib3.util.retry import Retry
            
            adapter = HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.2))
            session = requests.Session()
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            try:
                with session.get(url, timeout=(30, 300), stream=True) as r:
                    r.raise_for_status()
                    with open(dest_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
            except Exception as e:
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except:
                        pass
                raise ValueError(f"Failed to download video from {url}: {e}")
        else:
            print(f"[LoadVideoByUrl] Using cached video: {dest_path}")
            
        func_name = getattr(vhs_cls, "FUNCTION", "load_video")
        kwargs["video"] = filename
        
        # Instantiate the native node class securely (bypass __init__ if it fails to avoid masking exceptions)
        try:
            instance = vhs_cls()
        except Exception as inst_err:
            try:
                instance = vhs_cls.__new__(vhs_cls)
            except Exception:
                instance = None
            
        if instance is not None:
            func = getattr(instance, func_name)
        else:
            func = getattr(vhs_cls, func_name)
            
        # Execute the function outside of try-except block so that real execution/validation errors 
        # (e.g. video formatting errors, file not found) are raised transparently.
        return func(**kwargs)


# Dynamic output schema synchronization for exact matching at load time
vhs_cls = get_vhs_load_video_class()
if vhs_cls is not None:
    if hasattr(vhs_cls, "RETURN_TYPES"):
        LoadVideoByUrl.RETURN_TYPES = vhs_cls.RETURN_TYPES
    if hasattr(vhs_cls, "RETURN_NAMES"):
        LoadVideoByUrl.RETURN_NAMES = vhs_cls.RETURN_NAMES
