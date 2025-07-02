#!/usr/bin/env python3
"""Setup script for the Monzo API Python library."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="monzo-apy",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Python library for interacting with the Monzo API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/r3vrt/monzo-apy",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Office/Business :: Financial",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "responses>=0.13.0",
            "pytest-cov>=2.12.0",
            "black>=21.0.0",
            "flake8>=3.9.0",
            "isort>=5.9.0",
            "sphinx>=4.0.0",
            "sphinx-rtd-theme>=1.0.0",
            "mypy>=0.910",
        ],
    },
    keywords="monzo, api, banking, finance, python",
    project_urls={
        "Bug Reports": "https://github.com/r3vrt/monzo-apy/issues",
        "Source": "https://github.com/r3vrt/monzo-apy",
        "Documentation": "https://docs.monzo-apy.com",
    },
) 