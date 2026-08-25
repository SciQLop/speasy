#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for the upgrade-path CI job's helper scripts (.github/scripts/).
These scripts aren't part of the speasy package, so they're imported directly
off disk by path rather than as a normal package import."""
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "scripts"


def _load(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


upgrade_path_fetch = _load("upgrade_path_fetch", "upgrade_path_fetch.py")


class FakeVar:
    def __init__(self, length):
        self._length = length

    def __len__(self):
        return self._length


class FetchAmda(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="upgrade_path_test_")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.state_file = Path(self.tmpdir) / "state.json"

    def test_first_step_with_no_prior_state_succeeds_and_writes_state(self):
        get_data = mock.Mock(return_value=FakeVar(5400))

        upgrade_path_fetch.fetch_amda(get_data, step=0, state_file=self.state_file)

        self.assertEqual(json.loads(self.state_file.read_text()), {"amda_imf_length": 5400})

    def test_raises_when_result_is_empty(self):
        get_data = mock.Mock(return_value=FakeVar(0))

        with self.assertRaises(AssertionError):
            upgrade_path_fetch.fetch_amda(get_data, step=0, state_file=self.state_file)

    def test_raises_when_result_is_none(self):
        get_data = mock.Mock(return_value=None)

        with self.assertRaises(AssertionError):
            upgrade_path_fetch.fetch_amda(get_data, step=0, state_file=self.state_file)

    def test_growth_check_passes_when_length_increases(self):
        self.state_file.write_text(json.dumps({"amda_imf_length": 5400}))
        get_data = mock.Mock(return_value=FakeVar(8100))

        upgrade_path_fetch.fetch_amda(get_data, step=1, state_file=self.state_file)

        self.assertEqual(json.loads(self.state_file.read_text()), {"amda_imf_length": 8100})

    def test_growth_check_fails_when_length_does_not_increase(self):
        """A growing requested window that doesn't return more data means the
        merge of an older version's cached fragments with newly fetched ones
        likely silently dropped something -- this is the whole point of the
        job, so it must be a hard failure, not a warning."""
        self.state_file.write_text(json.dumps({"amda_imf_length": 8100}))
        get_data = mock.Mock(return_value=FakeVar(8100))

        with self.assertRaises(AssertionError):
            upgrade_path_fetch.fetch_amda(get_data, step=2, state_file=self.state_file)


class FetchSingleShot(unittest.TestCase):
    def test_succeeds_on_non_empty_result(self):
        get_data = mock.Mock(return_value=FakeVar(30))

        upgrade_path_fetch.fetch_single_shot(get_data, "ssc/moon", "2006-01-08T01:00:00",
                                             "2006-01-08T01:30:00")

        get_data.assert_called_once_with("ssc/moon", "2006-01-08T01:00:00", "2006-01-08T01:30:00")

    def test_raises_on_empty_result(self):
        get_data = mock.Mock(return_value=FakeVar(0))

        with self.assertRaises(AssertionError):
            upgrade_path_fetch.fetch_single_shot(get_data, "ssc/moon", "x", "y")


class Run(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="upgrade_path_run_test_")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.state_file = Path(self.tmpdir) / "state.json"

    def test_skips_providers_not_reported_by_list_providers(self):
        get_data = mock.Mock(return_value=FakeVar(10))
        list_providers = mock.Mock(return_value={"amda", "cda"})  # no ssc, no cdpp3dview

        upgrade_path_fetch.run(get_data, list_providers, step=0, state_file=self.state_file)

        called_products = {call.args[0] for call in get_data.call_args_list}
        self.assertIn("amda/imf", called_products)
        self.assertIn(upgrade_path_fetch.SINGLE_SHOT_PRODUCTS["cda"][0], called_products)
        self.assertNotIn(upgrade_path_fetch.SINGLE_SHOT_PRODUCTS["ssc"][0], called_products)
        self.assertNotIn(upgrade_path_fetch.SINGLE_SHOT_PRODUCTS["cdpp3dview"][0], called_products)

    def test_calls_every_configured_product_when_all_providers_available(self):
        get_data = mock.Mock(return_value=FakeVar(10))
        list_providers = mock.Mock(return_value={"amda", "cda", "ssc", "cdpp3dview"})

        upgrade_path_fetch.run(get_data, list_providers, step=0, state_file=self.state_file)

        called_products = {call.args[0] for call in get_data.call_args_list}
        expected = {"amda/imf"} | {p for p, _, _ in upgrade_path_fetch.SINGLE_SHOT_PRODUCTS.values()}
        self.assertEqual(called_products, expected)

    def test_single_shot_failure_is_logged_and_does_not_stop_the_loop(self):
        """cdpp3dview (and any other single-shot provider) is known less
        reliable than AMDA; one failing must not abort the whole run, and the
        remaining single-shot providers must still be tried."""
        failing_product = upgrade_path_fetch.SINGLE_SHOT_PRODUCTS["cda"][0]

        def side_effect(product, start, stop):
            if product == failing_product:
                return FakeVar(0)
            return FakeVar(10)

        get_data = mock.Mock(side_effect=side_effect)
        list_providers = mock.Mock(return_value={"amda", "cda", "ssc", "cdpp3dview"})

        upgrade_path_fetch.run(get_data, list_providers, step=0, state_file=self.state_file)

        called_products = {call.args[0] for call in get_data.call_args_list}
        expected = {"amda/imf"} | {p for p, _, _ in upgrade_path_fetch.SINGLE_SHOT_PRODUCTS.values()}
        self.assertEqual(called_products, expected)

    def test_fetch_amda_failure_still_propagates(self):
        """Unlike the single-shot providers, amda/imf is the stateful
        growth-check anchor -- its failures must remain hard."""
        def side_effect(product, start, stop):
            if product == "amda/imf":
                return FakeVar(0)
            return FakeVar(10)

        get_data = mock.Mock(side_effect=side_effect)
        list_providers = mock.Mock(return_value={"amda", "cda", "ssc", "cdpp3dview"})

        with self.assertRaises(AssertionError):
            upgrade_path_fetch.run(get_data, list_providers, step=0, state_file=self.state_file)


upgrade_path_driver = _load("upgrade_path_driver", "upgrade_path_driver.py")


class InstallTarget(unittest.TestCase):
    def test_main_uses_the_checked_out_repo_root(self):
        """install_target() just returns str(repo_root) -- compare against that,
        not a hardcoded POSIX literal: str(Path("/repo")) renders as "\\repo" on
        Windows, not "/repo", so a literal comparison fails there deterministically."""
        repo_root = Path("/repo")

        self.assertEqual(upgrade_path_driver.install_target("main", repo_root), str(repo_root))

    def test_pinned_version_uses_a_pypi_spec(self):
        repo_root = Path("/repo")

        self.assertEqual(upgrade_path_driver.install_target("1.5.2", repo_root), "speasy==1.5.2")


class RunSteps(unittest.TestCase):
    def test_installs_and_fetches_each_version_in_order(self):
        installer_calls = []
        runner_calls = []

        def fake_installer(version, repo_root, runner):
            installer_calls.append(version)

        def fake_runner(cmd, check):
            runner_calls.append(cmd)

        upgrade_path_driver.run_steps(
            versions=["1.5.2", "1.7.1", "main"],
            repo_root=Path("/repo"),
            fetch_script=Path("/repo/.github/scripts/upgrade_path_fetch.py"),
            state_file="state.json",
            installer=fake_installer,
            runner=fake_runner,
        )

        self.assertEqual(installer_calls, ["1.5.2", "1.7.1", "main"])
        # cmd shape: [sys.executable, fetch_script, "--step", step, "--state-file", state_file]
        self.assertEqual([call[2] for call in runner_calls], ["--step", "--step", "--step"])
        self.assertEqual([call[3] for call in runner_calls], ["0", "1", "2"])


if __name__ == "__main__":
    unittest.main()
