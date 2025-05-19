#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name="midscene-python-bridge",
    version="0.1.0",
    description="Python客户端实现，用于连接MidScene Chrome扩展",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="MidScene",
    packages=find_packages(),
    install_requires=[
        "websockets>=10.0",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.6",
) 