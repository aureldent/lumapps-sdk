from io import open
from setuptools import setup, find_packages
from lumapps.config import __version__, __pypi_packagename__


def read_file(file_path):
    with open(file_path, "r") as f:
        content = f.read()
    return content


install_requires = ["requests==2.20.1", "google-api-python-client==1.7.7"]
readme = read_file("README.rst")

setup(
    name=__pypi_packagename__,
    version=__version__,
    author="LumApps",
    url="https://github.com/lumapps/lumapps-sdk",
    packages=find_packages(exclude=["documentation", "tests", "examples"]),
    include_package_data=True,
    license="MIT",
    description="Lumapps SDK for Python",
    long_description=readme,
    long_description_content_type="text/x-rst",
    install_requires=install_requires,
    python_requires=">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5.*",
    keywords="lumapps sdk",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    project_urls={
        "Documentation": "https://lumapps.github.io/lumapps-sdk/",
        "Source": "https://github.com/lumapps/lumapps-sdk",
        "Issues": "https://github.com/lumapps/lumapps-sdk/issues",
        "CI": "https://circleci.com/gh/lumapps/lumapps-sdk",
    },
    entry_points={
        "console_scripts": ["client=lumapps.cli:main", "lac=lumapps.cli:main"]
    },
)
