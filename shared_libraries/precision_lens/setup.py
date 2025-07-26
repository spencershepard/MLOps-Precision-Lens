from setuptools import setup, find_packages

setup(
    name="precision_lens",
    version="0.2.0",
    description="Shared utilities for MLOps-Precision-Lens",
    author="spencershepard",
    packages=find_packages(),
    install_requires=[
        "boto3",
        "botocore"
    ],
    python_requires=">=3.8",
)