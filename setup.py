from setuptools import setup
from setuptools import find_packages


def readme():
    with open('README.md', encoding='utf-8') as file:
        return file.read()


setup(
    name='LocText',
    version='1.0.1',
    description='NLP-based Relation Extraction (RE) of: Proteins <--> Cell Compartments',
    long_description=readme(),
    url='https://github.com/Rostlab/LocText',
    author='Juan Miguel Cejuela, Shrikant Vinchurkar',
    author_email='loctext@rostlab.org',

    packages=find_packages(exclude=['tests']),

    test_suite='pytest-runner',
    setup_requires=['pytest'],

    dependency_links=[
        'git+https://github.com/Rostlab/nalaf.git@feature/performance_check#egg=nalaf'
    ],

    install_requires=[
        # ML
        'nalaf == 0.2.2',
        'numpy == 1.11.2',
        'scipy == 0.18.1',  # or 0.19.0
        'scikit-learn == 0.18.1',
        'spacy == 1.2.0',
        'nltk == 3.4.5',

        # Other
        'requests',
        'requests_cache >= 0.4.13',
        'ujson',  # It should be included with spacy, AFAIK
    ]
)
