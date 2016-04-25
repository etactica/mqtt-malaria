from setuptools import setup
import os
import version

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='mqtt-malaria',
    url="https://github.com/remakeelectric/mqtt-malaria",
    maintainer="ReMake Electric ehf. - Software Department",
    maintainer_email="software@remake.is",
    version=version.get_git_version(),
    description="Attacking MQTT systems with Mosquittos",
    long_description=read('README.md'),
    license="License :: OSI Approved :: BSD License",
    scripts=["malaria"],
    packages=[
        'beem',
        'beem.cmds'
    ],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'paho-mqtt>=1.1',
        'fusepy'
    ],
    tests_require=[
        'fabric',
        'fabtools',
        'nose',
        'coverage'
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Testing :: Traffic Generation",
        "Topic :: System :: Benchmark",
        "Topic :: System :: Networking"
    ]
)
