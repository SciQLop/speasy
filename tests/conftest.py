import os

if "SPEASY_CORE_DISABLED_PROVIDERS" not in os.environ:
        os.environ['SPEASY_CORE_DISABLED_PROVIDERS'] = ""
