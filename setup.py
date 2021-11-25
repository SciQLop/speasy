#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = ['Click>=6.0', 'requests', 'zeep', 'xmltodict', 'pandas', 'diskcache', 'appdirs', 'numpy',
                'packaging', 'python-dateutil', 'astropy', 'spwc']

setup_requirements = []

test_requirements = ['pytest', 'ddt']

setup(
    author="Alexis Jeandet",
    author_email='alexis.jeandet@member.fsf.org',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ],
    description="A simple Python package to deal with main Space Physics WebServices (CDA,CSA,AMDA,..) mainly written to ease development of SciQLop.",
    entry_points={
        'console_scripts': [
            'speasy=speasy.cli:main',
        ],
    },
    install_requires=requirements,
    extras_require={'CDF':  ["spacepy"]},
    license="GNU General Public License v3",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='speasy',
    name='speasy',
    packages=find_packages(include=['speasy','speasy.amda','speasy.cache','speasy.cdaweb','speasy.common','speasy.config',
                                    'speasy.sscweb','speasy.proxy']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/SciQLop/speasy',
    version='0.9.1',
    zip_safe=False,
)
