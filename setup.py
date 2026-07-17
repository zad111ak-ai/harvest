from setuptools import setup, find_packages

setup(
    name="harvest",
    version="0.4.0",
    description="Universal web collection engine — scrape, extract, monitor, crawl with Cloudflare bypass",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="zad111ak-ai",
    author_email="zad111ak@gmail.com",
    url="https://github.com/zad111ak-ai/harvest",
    packages=find_packages(),
    install_requires=[
        "scrapling>=0.4.9",
        "beautifulsoup4>=4.12",
        "httpx>=0.27",
    ],
    extras_require={
        "crawl4ai": ["crawl4ai>=0.9.0"],
        "all": ["scrapling[all]>=0.4.9", "crawl4ai>=0.9.0"],
    },
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
