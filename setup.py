from setuptools import setup

version = '1.4.0'

setup(
    name='sql-schema-builder',
    packages = ['sql_schema_builder'],
    version=version,
    description='Library to keep SQL database schema up to date with your code.',
    author='Ganymede',
    author_email='mmeinardi@ganymede.eu',
    license='Apache License, Version 2.0',
    url='https://github.com/mmeinardi-ganymede/sql-schema-builder',
    download_url='https://github.com/mmeinardi-ganymede/sql-schema-builder/tarball/{0}'.format(version),
    keywords=['pymysql sql schema builder mysql ddl migration migrate'],
    install_requires=['pymysql']
)
