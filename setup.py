from setuptools import setup, find_packages

setup(
    name="ara1-financial-research-agent",
    version="0.1.0",
    description="Autonomous Financial Research Agent with Multi-Source Synthesis (ARA-1)",
    author="QuantumEdge Research / Zetheta Intern",
    packages=find_packages(include=["agent*", "tools*", "memory*", "synthesis*", "evaluation*"]),
    python_requires=">=3.10",
)
