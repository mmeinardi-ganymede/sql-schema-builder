
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
