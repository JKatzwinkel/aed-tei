from distutils.core import setup

setup(
    name='peret',
    install_requires=[
        'delb[https-loader]==0.3.0',
        'xmlschema',
        'requests',
        'docopt',
    ],
    extras_require={
        'test': [
            'pytest',
        ]
    },
    entry_points={
        'console_scripts': (
            'peret = peret:main',
            'shemu = peret.validate:main',
        )
    },
    packages=['peret'],
)
