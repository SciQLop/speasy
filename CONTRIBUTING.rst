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
   recommended). Then install the development requirements::

    $ cd speasy/
    $ python -m venv venv # Create a virtual environment inside Speasy directory
    $ source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    $ python -m pip install -e .
    $ python -m pip install -r requirements_dev.txt

4. Create a branch for local development::

    $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass flake8 and the
   tests, including testing other Python versions with tox::

    $ make lint
    $ make test-all # it will run all tests and run code examples in the docs

    Alternatively, if just want to run quick tests for the current Python version, run::

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
   feature to the list in README.rst.
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

Tips
----

To run a subset of tests::

$ py.test tests.test_speasy


Deploying
---------

A reminder for the maintainers on how to deploy.
Make sure all your changes are committed (including an entry in HISTORY.rst).
Then run::

$ bumpversion patch # possible: major / minor / patch
$ git push
$ git push --tags

GH Actions will then deploy to PyPI if tests pass.
