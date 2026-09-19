.. highlight:: shell

============
Contributing
============

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/SciQLop/speasy/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug" and "help
wanted" is open to whoever wants to implement it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

Speasy could always use more documentation, whether as part of the
official Speasy docs, in docstrings, or even on the web in blog posts,
articles, and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at https://github.com/SciQLop/speasy/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

If you are fixing a bug, remember to include a test that reproduces the bug first. You can
point to the issue that you are fixing in the non regression test.

Get Started!
------------

Ready to contribute? Here's how to set up `Speasy` for local development.

1. Fork the `Speasy` repo on GitHub.
2. Clone your fork locally::

    $ git clone git@github.com:your_name_here/speasy.git

3. Install your local copy into a virtual environment if you use one (highly
   recommended). Then install the development environment with UV::

    $ uv sync --group dev --group docs

   This installs Speasy editable plus all dev and docs dependencies in
   a managed virtualenv (``.venv/``). Run commands via ``uv run`` (e.g.
   ``uv run pytest``) or activate the venv with ``source .venv/bin/activate``.

4. Create a branch for local development::

    $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass flake8 and the
   tests::

    $ make lint
    $ make test
    $ make doctest


6. Commit your changes and push your branch to GitHub::

    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin name-of-your-bugfix-or-feature

7. Submit a pull request through the GitHub website.

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in README.md.
3. The pull request should work for Python from 3.10 to 3.14. Check
   https://github.com/SciQLop/speasy/actions
   and make sure that the tests pass for all supported Python versions.

Coding guidelines
-----------------

* Follow PEP 8 style guidelines. You can use `flake8` to check your code.
* Use `numpy` docstring style for docstrings.
* Write docstrings for any new functions or classes you add. Follow the existing style. Those docstrings will be used to generate the developers documentation.
* Write tests for any new functionality you add. Look at existing tests for examples.
* Reuse as much as possible existing functionalities from `speasy.core`. For example,
  if you need to do some web requests, use the `speasy.core.http` module.
* If you want to add a new data provider, follow the existing structure in the `speasy.data_providers` module.
  You can have a look at existing providers such as sscweb or uiowa_eph_tool for reference.
* If you want to add a new data format, create a new CODEC in the `speasy.core.codecs` module.
  See "Adding support for a new file format" in the direct archive access docs
  (`docs/user/direct_archive/direct_archive.rst`) for the full ``CodecInterface`` contract,
  registration mechanism, and a worked example.

Tips
----

To run a subset of tests::

$ py.test tests.test_speasy


Deploying
---------

A reminder for the maintainers on how to deploy.

The version is not stored anywhere: it is derived from ``git describe``, so the
tag *is* the version. Publishing the GitHub release is what triggers the PyPI
upload (``.github/workflows/pythonpublish.yml`` runs on ``release: published``)
and the Zenodo DOI. Pushing the tag alone does neither.

1. Finalize the release commit on ``main``: date the version's section in
   ``HISTORY.rst`` and set ``version`` and ``date-released`` in ``CITATION.cff``.
   Leave ``doi`` as is, the new one does not exist yet. Push and wait for CI::

      $ git push upstream main

2. Tag and publish the release. The notes are the ``HISTORY.rst`` section in
   Markdown::

      $ git tag v1.2.3        # the release version, no suffix
      $ git push upstream v1.2.3
      $ gh release create v1.2.3 --verify-tag --notes-file notes.md

3. Wait for the Zenodo record, usually about a minute::

      $ curl -s "https://zenodo.org/api/records?q=conceptrecid:4118780&sort=mostrecent&size=1" \
          | jq -r '.hits.hits[0] | "\(.metadata.version) \(.doi)"'

   Put the new DOI in ``CITATION.cff`` and push that commit.

4. Open the next cycle by tagging the DOI commit::

      $ git tag v1.3.0.dev0
      $ git push upstream v1.3.0.dev0

   The dev tag must sit on a commit *after* the release tag. On the release
   commit itself ``git describe`` keeps picking ``v1.2.3`` and the dev tag is
   ignored (this happened for 1.8.2.dev0). Until a dev tag exists, commits
   after ``v1.2.3`` report ``1.2.3.post<n>.dev0`` rather than ``1.3.0.dev<n>``.
