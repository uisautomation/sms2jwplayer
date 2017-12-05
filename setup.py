from setuptools import setup, find_packages

setup(
    name='sms2jwplayer',
    author='University of Cambridge Information Services',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'sms2jwplayer=sms2jwplayer:main',
        ],
    },
    install_requires=[
        'Jinja2',
        'docopt',
        'jwplatform',
        'python-dateutil',
    ],
)
