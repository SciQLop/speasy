try:
    from spacepy import pycdf
    have_cdf = True
    from .__cdf__ import load_cdf
except ImportError:
    have_cdf = False
