import unittest
import os
try:
    from teamcity import is_running_under_teamcity
    from teamcity.unittestpy import TeamcityTestRunner
except ImportError:
    def is_running_under_teamcity():
        return False

if __name__ == '__main__':
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        runner = unittest.TextTestRunner()
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.dirname(os.path.abspath(__file__)))
    runner.run(suite)
