from setuptools import setup, find_packages

setup(
    name="harvest",
    version="0.3.0",
    description="Universal web collection engine — scrape, monitor, and extract data from any website",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="zad111ak-ai",
    author_email="zad111ak@gmail.com",
    url="https://github.com/zad111ak-ai/harvest",
    packages=find_packages(),
    install_requires=["scrapling>=0.4.9"],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "harvest=harvest.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
