import unittest
from unittest import mock

from speasy.core import plugins


def _entry_point(name, target=None, load_error=None):
    """A stand-in for importlib.metadata.EntryPoint: .name, .value, .load()."""
    ep = mock.MagicMock()
    ep.name = name
    ep.value = f"{name}_pkg:register"
    if load_error is not None:
        ep.load.side_effect = load_error
    else:
        ep.load.return_value = target
    return ep


class LoadPlugins(unittest.TestCase):

    def test_loads_and_calls_every_entry_point(self):
        first, second = mock.MagicMock(), mock.MagicMock()
        eps = [_entry_point("first", first), _entry_point("second", second)]
        with mock.patch.object(plugins, "entry_points", return_value=eps) as entry_points:
            plugins.load_plugins("speasy.codecs")
        entry_points.assert_called_once_with(group="speasy.codecs")
        first.assert_called_once_with()
        second.assert_called_once_with()

    def test_a_plugin_failing_to_load_does_not_stop_the_others(self):
        survivor = mock.MagicMock()
        eps = [_entry_point("broken", load_error=ImportError("missing dep")),
               _entry_point("survivor", survivor)]
        with mock.patch.object(plugins, "entry_points", return_value=eps):
            with self.assertLogs("speasy.core.plugins", level="WARNING") as captured:
                plugins.load_plugins("speasy.codecs")
        survivor.assert_called_once_with()
        self.assertIn("broken", captured.output[0])

    def test_a_plugin_raising_when_called_does_not_stop_the_others(self):
        survivor = mock.MagicMock()
        eps = [_entry_point("raises", mock.MagicMock(side_effect=ValueError("collision"))),
               _entry_point("survivor", survivor)]
        with mock.patch.object(plugins, "entry_points", return_value=eps):
            with self.assertLogs("speasy.core.plugins", level="WARNING") as captured:
                plugins.load_plugins("speasy.codecs")
        survivor.assert_called_once_with()
        self.assertIn("raises", captured.output[0])

    def test_a_disabled_plugin_is_never_loaded(self):
        disabled = _entry_point("unwanted")
        with mock.patch.object(plugins, "entry_points", return_value=[disabled]):
            with mock.patch.object(plugins.core_cfg.disabled_plugins, "get", return_value={"unwanted"}):
                plugins.load_plugins("speasy.codecs")
        disabled.load.assert_not_called()

    def test_an_empty_group_is_a_no_op(self):
        with mock.patch.object(plugins, "entry_points", return_value=[]):
            plugins.load_plugins("speasy.virtual_products")

    def test_a_group_qualified_name_disables_the_plugin_in_that_group(self):
        disabled = _entry_point("my_format")
        with mock.patch.object(plugins, "entry_points", return_value=[disabled]):
            with mock.patch.object(plugins.core_cfg.disabled_plugins, "get",
                                   return_value={"speasy.codecs.my_format"}):
                plugins.load_plugins("speasy.codecs")
        disabled.load.assert_not_called()

    def test_a_name_qualified_with_another_group_does_not_disable_it_here(self):
        target = mock.MagicMock()
        homonym = _entry_point("my_format", target)
        with mock.patch.object(plugins, "entry_points", return_value=[homonym]):
            with mock.patch.object(plugins.core_cfg.disabled_plugins, "get",
                                   return_value={"speasy.virtual_products.my_format"}):
                plugins.load_plugins("speasy.codecs")
        target.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
