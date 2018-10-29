from setuptools import setup

# TODO copy secrets.py.template to secrets.py

setup(
    name="aprsistrack",
    version=0.1,
    author='Luke Renegar',
    author_email='luke.renegar@gmail.com',
    packages=['aprsistrack'],
    zip_safe=False,
    license='Apache 2.0',
    description='APRS-IS Tracking API',
    install_requires=["Flask"],
)
