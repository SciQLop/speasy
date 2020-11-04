try:
    from spacepy import pycdf
    have_cdf = False #ignore cdf for now
    from .__cdf__ import load_cdf
except ImportError:
    have_cdf = False
