# sql-schema-builder

## What is it?

`sql-schema-builder` is a python library that helps with the task of keeping SQL schema up to date
with your application code.
Instead of writing separate SQL scripts to create/migrate your schema, you can define the schema in simple DDL form
in your code and let `sql-schema-builder` do the work of keeping it always up to date.

Thanks to that, you don't have to run separate migration scripts in every environment,
and when you ship update of your application to production, your database schema will be automatically upgraded
to newest schema.

The big benefit of keeping the schema inside your code is that it is right there in the same version control
system of your choice - along with history of all changes made to it. You don't need to synchronize changes
in your app code, some other sql schema keeping scripts and the database.


## Idea

The idea is that you define schema for your SQL tables in simple Data Definition Language in your application code.
After connecting to the database, the library will check current version number of the database schema
(stored in `cfg_dbase` table).
If it is older than the version defined in your code, the library will find the differences in table definitions
and automatically issue all ALTER statements to bring your schema up to date.

This idea came from using [AdoDB](http://adodb.org) library for PHP which has very useful
[`ChangeTableSQL()`](http://adodb.org/dokuwiki/doku.php?id=v5:dictionary:changetablesql) function.
Unfortunately I haven't found any similarly working lightweight library for python that isn't part of some big framework
like [django](https://www.djangoproject.com/) or [web2py](http://www.web2py.com/).


## Installation/upgrade

    pip install -U sql-schema-builder

The library is compatible with python 2.7+ and python 3.4+.


## Example usage ([example-quickstart.py](./examples/example-quickstart.py))

```python
from sql_schema_builder.SQLSchemaBuilder import SQLSchemaBuilder

def _get_schema():

    schema = {}
    schema_version = 1.019

    schema['teams'] = """
        id_team I NOTNULL DEFAULT 0,
        name C(32),
        coach_name C(64),

        points I,
        matches_won I,
        matches_drawn I,
        matches_lost I,

        timestamp_updated I8,
        INDEX PRIMARY (id_team),
        INDEX (timestamp_updated)
    """

    schema['players'] = """
        id_player I NOTNULL DEFAULT 0,
        name C(64),
        id_team I NOTNULL,

        shirt_number I,
        position ENUM('', 'goalkeeper', 'defender', 'midfielder', 'forward') DEFAULT '',

        goals_scored I,

        height I,
        weight F,

        INDEX PRIMARY (id_player),
        INDEX (id_team, position, shirt_number)
    """

    return schema, schema_version

db_schema = SQLSchemaBuilder(host='localhost', port=3306, user='root', passwd='xxx', db='premierleague')
db_schema.UpdateSchema(*_get_schema())
```

`I` stands for integer, `I8` for big integer, `C` for varchar, `F` for float etc. ([DDL reference](#ddl))

Now, whenever you need to add some new table, column, index or alter them (e.g. drop or change column's type/order) you
just edit above schema, increase its version number (to e.g. 1.020) and you're done.


## Quick start

The above sample code is all you need to get started.
A little bigger example that also illustrates [data migration convention](#data-migrations) can be found in the
[examples](./examples/example-datamigration.py) directory.


## Comparison with other schema migration tools

Some other tools in the category exist in the python ecosystem:
[alembic](https://pypi.python.org/pypi/alembic),
[sqlalchemy-migrate](https://pypi.python.org/pypi/sqlalchemy-migrate/),
[sqlturk](https://pypi.python.org/pypi/sqlturk),
[yoyo-migrations](https://pypi.python.org/pypi/yoyo-migrations),
[mschematool](https://pypi.python.org/pypi/mschematool/).
Full-stack frameworks like [django](https://www.djangoproject.com/) or [web2py](http://www.web2py.com/)
also have their own way of solving the problem. So, why would someone choose `sql-schema-builder`?

- **No need to deploy and run any separate migration script.**

The method works even if you e.g. don't have ssh access to your client/customer environment.
You can send your updated application code and the schema will be brought up to date after the first run.

- **No need to write migration queries/scripts with every little change.**

Often incremental changes to the schema are minimal and non-intrusive such as adding new table, new column
or modifying column's type e.g. widening VARCHAR field or adding new ENUM value.
Writing separate migration script for each such change is far from enjoyable. Especially when
you end up with dozens of them for simple database during development.

- **Zero configuration.**

The only thing you need to pass to the library are address and credentials to your database.
No separate config options/files. It just works.

- **No need to install "big" tool/framework and learn its philosophy.**

`sql-schema-builder` is just a small library that does one job - helps to keep your database schema up to date.
This is just a library not a separate tool.

- **Framework-agnostic.**

The library is framework-agnostic and it doesn't force or expect any ORM model.
It can be used alongside any framework of your choice.
Its primary intent was to be used in web services written in non full-stack frameworks such as
[web.py](http://webpy.org/), [flask](http://flask.pocoo.org/) etc.


## Shortcomings

- So far only MySQL support.

- Not all column types are supported.

It's very easy to add new types when the need arises. Just modify `UpdateTableSchema()` function
in file [MySQLSchema.py](./sql_schema_builder/MySQLSchema.py)
and make a pull-request.

- Extra SELECT query after connecting to the database.

There is a little overhead for using the library as we have to check current schema version every time
your application runs. The overhead is minimal as it is only one SELECT from very small table.
If you open connection to the database only at your application start and keep it open this will be negligible.
If you do it on every request to your service it may or may not pose a problem for you.

- No rollback feature.

This is _by design_, as I agree with [sqlturk](https://pypi.python.org/pypi/sqlturk) author's point of view, that downgrade
scripts may add more problems than they solve.


## Data migrations

In case you need to modify or initialize some data in your schema after the migration, you can write code similar to this:

```python
def _get_schema():

    schema_version = 1.020

    schema['teams'] = """
        ...
        total_goals I,
        ...
    """

    ...

def _migrate_schema(db_schema_version, cursor):

    if db_schema_version < 1.020:
        sql = """SELECT id_team, SUM(goals_scored) FROM players GROUP BY id_team"""
        cursor.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            sql = """UPDATE teams SET total_goals = %s WHERE id_team = %s AND total_goals IS NULL"""
            cursor.execute(sql, (row[1], row[0]))

db_schema = SQLSchemaBuilder(host='localhost', port=3306, user='root', passwd='xxx', db='premierleague')
db_schema.UpdateSchema(_get_schema(), post_migrate_callback=_migrate_schema)
```

You can write many more `if` statements like this in `_migrate_schema()` function to bring data in your database
to desired state after migration from previous schema version.

Parameter `db_schema_version` is the old schema version that database schema was up to, before migration happened.

Parameter `cursor` is [PyMySQL](https://github.com/PyMySQL/PyMySQL) cursor which you can use to alter data in your database.
The `post_migrate_callback` will be called inside transaction, so you don't have to commit your queries.
If you explicitly `return False` from the callback, the `UpdateSchema()` will also return `False`.
In that case schema version in the database will not be increased, but all schema manipulations will be done anyway.
That's because
[MySQL doesn't support transactional schema changes](http://stackoverflow.com/questions/4692690/is-it-possible-to-roll-back-create-table-and-alter-table-statements-in-major-sql).


## Reference

### Classes (only 1 class actually :smile:)

`SQLSchemaBuilder`

* `SQLSchemaBuilder(host=None, port=3306, user=None, passwd=None, db=None, pymysql_conn=None, create_db=False)`

    - Class constructor that expects address and credentials to the database on which schema you wish to operate on.
    If you are using [PyMySQL](https://github.com/PyMySQL/PyMySQL), you can alternatively pass its opened connection
    object as `pymysql_conn` parameter. The advantage of this is that you can reuse the same connection
    for schema manipulation and later data access.
    Parameters:
        * `create_db` - If set to `True` and the database doesn't exist yet, it will be created.

* `UpdateSchema(schema_dict, schema_version, post_migrate_callback=None, pre_migrate_callback=None)`

    - Main function that checks if your database schema is up to date and issues CREATE/ALTER statements if necessary.
    Parameters:
        * `schema_dict` - Dictionary that maps table name to its schema definition (for the format see the provided
        [example](./examples/example-quickstart.py)).
        * `schema_version` - A number (integer or float) that should increase with every change to the schema.

    - The schema version will be stored in your database in the table `cfg_dbase` that will be created if it doesn't exist.

    - You can pass `post_migrate_callback` which is a callback that will be called after schema migration is done.
    Its declaration has 2 parameters:

        `def post_migrate_callback(db_schema_version, cursor)`

        * `db_schema_version` is the version of the schema *before* migration.
        * `cursor` is a [PyMySQL](https://github.com/PyMySQL/PyMySQL) cursor which you can execute sql statements on.

    - The function doesn't alter/drop any tables it doesn't know about.
    So if you want to drop the table, remove it from your code, and execute DROP TABLE in the `post_migrate_callback`.

    - There is also parameter `pre_migrate_callback` analogous to `post_migrate_callback`, but called before
        migrating the schema. Its primary use case is for column renaming. If you would just rename column in DDL,
        the library would drop the old column and create new one losing the contents. To avoid this, you should issue
        proper ALTER TABLE statement that renames the column, before the schema migration will take place.
        If you explicitly `return False` from the callback, the rest of the migration will be abandoned.

    - Return values:
        - `True` - Schema upgrade succeeded or was already up to date.
        - `False` - Couldn't connect to database or failed to upgrade database schema.
            In that case it's more likely that one of the following exceptions will be raised describing the error:
            `ValueError`, `pymysql.err.DatabaseError`, `pymysql.err.ProgrammingError`.

### DDL

Available abbreviations and MySQL types they represent in DDL:

| abbrev. | meaning |
| -------- | -------- |
| `I` | `INT(11)` |
| `I1` | `TINYINT(4)` |
| `I2` | `SMALLINT(6)` |
| `I8` | `BIGINT(20)` |
| `F` | `DOUBLE` |
| `N` | `DECIMAL(10,2)` |
| `C(n)` | `VARCHAR(n)` |
| `MX` | `MEDIUMTEXT` |
| `X` | `LONGTEXT` |
| `MB` | `MEDIUMBLOB` |
| `B` | `LONGBLOB` |
| `BIN(n)` | `BINARY(n)` |
| `J` | `JSON` |
| `D` | `DATE` |
| `T` | `DATETIME` |
| `ENUM(...)` | `ENUM(...)` |

You can use following attributes on columns (in that particular order):

- `UNSIGNED`
- `AUTO_INCREMENT`
- `NOTNULL`
- `DEFAULT x`

Following INDEX attributes are supported:

- `PRIMARY`
- `UNIQUE`
