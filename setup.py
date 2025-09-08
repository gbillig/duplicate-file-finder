"""
Setup configuration for duplicate-file-finder package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    # Remove comments from requirements
    requirements = [req.split("#")[0].strip() for req in requirements]

setup(
    name="duplicate-file-finder",
    version="1.0.0",
    author="Gleb Billig",
    author_email="",
    description="A high-performance tool for finding duplicate files and folders",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gbillig/duplicate-file-finder",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Filesystems",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "duplicate-finder=duplicate_finder.cli:main",
        ],
    },
    keywords="duplicate files finder deduplication filesystem utility",
    project_urls={
        "Bug Reports": "https://github.com/gbillig/duplicate-file-finder/issues",
        "Source": "https://github.com/gbillig/duplicate-file-finder",
    },
)