from setuptools import setup, find_packages

setup(
    name='llm-obs',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        # Add your project dependencies here
    ],
    entry_points={
        'console_scripts': [
            # Add your command line scripts here
        ],
    },
    author='UArizonaSpace4',
    author_email='vrodriguezf@arizona.edu',
    description='LLMs as a Natural User Interface for the SDA observation pipeline',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/UArizonaSpace4/llm-obs',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.11',
)