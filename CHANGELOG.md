
## 1.5.1 (2020-04-27)

* Added more quoting of column names in SQL queries.


## 1.5.0 (2020-01-29)

+ Ability to use parameters `password`/`database` instead of `passwd`/`db` in `SQLSchemaBuilder()` constructor.

+ Add longer aliases for column types in DDL, e.g. `INT64`, `TEXT`.

* Better schema change detection in `ENUM` columns - independent of whitespaces used between values.


## 1.4.1 (2020-01-28)

+ Use default character set `utf8mb4` and default collate `utf8mb4_unicode_ci` for newly created databases.


## 1.4.0 (2020-01-15)

+ Ability to automatically create new database.


## 1.3.2 (2019-12-10)

* Fix quoting of column names read from table indexes. Don't recreate indexes when not necessary.


## 1.3.1 (2019-03-12)

* Added more quoting of column names in SQL queries.


## 1.3.0 (2019-03-07)

+ Added support for MySQL column types: `MEDIUMTEXT`, `MEDIUMBLOB`, `BINARY`.
+ Added support for MySQL column attribute: `UNSIGNED`.
* Added quoting of column names in SQL queries.


## 1.2.1 (2017-04-07)

* Fix internal import path.


## 1.2.0 (2017-04-04)

+ Rename `migrate_function` to `post_migrate_callback`. Added `pre_migrate_callback`.


## 1.1.0 (2017-04-03)

+ Ability to reorder columns.
* Proper handling of changes to INDEX PRIMARY with AUTO_INCREMENT column.


## 1.0.1 (2017-04-02)

* Fix pymysql requirement in package manifest.


## 1.0.0 (2017-04-02)

Initial sql-schema-builder version.
