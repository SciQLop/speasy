from functools import lru_cache


@lru_cache(maxsize=1)
def is_running_on_wasm() -> bool:
    import platform
    return platform.system().lower() == "emscripten"
