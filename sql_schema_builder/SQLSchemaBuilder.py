from sql_schema_builder.MySQLSchema import MySQLSchema
from sql_schema_builder.PgSQLSchema import PgSQLSchema

import pymysql
import psycopg


class SQLSchemaBuilder:

    # Supported db_type: "mysql", "pgsql".
    def __init__(self, host=None, port=3306, user=None,
                       passwd=None, password=None,
                       db=None, database=None,
                       pymysql_conn=None, create_db=False,
                       db_type="mysql"):
        self._conn = None
        self._conn_params = {}
        passwd = passwd or password
        db = db or database
        if db_type not in ["mysql", "pgsql"]:
            raise NotImplementedError(f"Unsupported db_type: {db_type}!")
        self.db_type = db_type

        if self.db_type == "mysql" and pymysql_conn is not None:
            self._conn = pymysql_conn
        else:
            self._conn_params = {
                'host': host,
                'port': port,
                'user': user,
                'passwd': passwd,
                'db': db if not create_db else None,
            }
        if create_db:
            self._create_database(db)

    def _create_database(self, db_name):
        self._connect_to_database()
        if self._conn is None:
            return

        db_exists = False
        with self._conn.cursor() as cursor:
            try:
                if self.db_type == "mysql":
                    sql = "SHOW DATABASES LIKE %s"
                elif self.db_type == "pgsql":
                    sql = "SELECT datname FROM pg_database WHERE datistemplate = false AND datname = %s"
                cursor.execute(sql, (db_name,))
                if cursor.fetchone() is not None:
                    db_exists = True
            except Exception as e:
                pass

        if not db_exists:
            if self.db_type == "pgsql":
                self._conn.commit()
                self._conn.autocommit = True

            with self._conn.cursor() as cursor:
                try:
                    if self.db_type == "mysql":
                        sql = f"CREATE DATABASE IF NOT EXISTS `{db_name}`"
                        sql += " DEFAULT CHARACTER SET `utf8mb4`"
                        sql += " DEFAULT COLLATE `utf8mb4_unicode_ci`"
                    elif self.db_type == "pgsql":
                        sql = f"CREATE DATABASE {db_name} WITH ENCODING = 'UTF8'"
                    cursor.execute(sql)
                except Exception as e:
                    pass

        self._conn.close()
        self._conn = None
        self._conn_params["db"] = db_name
        self._connect_to_database()

    def _connect_to_database(self):

        if self._conn is not None:
            return self._conn

        if self.db_type == "mysql":
            try:
                self._conn = pymysql.connect(
                    host=self._conn_params['host'],
                    port=self._conn_params['port'],
                    user=self._conn_params['user'],
                    passwd=self._conn_params['passwd'],
                    db=self._conn_params['db'],
                    charset='utf8mb4',
                    autocommit=False)
            except pymysql.err.DatabaseError:
                self._conn = None
                raise
        elif self.db_type == "pgsql":
            try:
                self._conn = psycopg.connect(
                    host=self._conn_params['host'],
                    port=self._conn_params['port'],
                    user=self._conn_params['user'],
                    password=self._conn_params['passwd'],
                    dbname=self._conn_params['db'] or "postgres",
                    autocommit=False)
            except psycopg.errors.DatabaseError:
                self._conn = None
                raise

        return self._conn

    def __del__(self):
        if self._conn is not None and self._conn_params:
            self._conn.close()
            self._conn = None

    def UpdateSchema(self, schema_dict, schema_version, post_migrate_callback=None, pre_migrate_callback=None):

        self._connect_to_database()
        if self._conn is None:
            return False

        if schema_dict is None or schema_version is None:
            return True

        if 'cfg_dbase' in schema_dict:
            return False

        schema_dict['cfg_dbase'] = """
            name C(64),
            value C(64),
            INDEX PRIMARY (name)
        """

        #-----------------------------------------------------------------------------------------------------------

        with self._conn.cursor() as cursor:

            try:
                sql = "SELECT value FROM cfg_dbase WHERE name = %s"
                cursor.execute(sql, ('schema_version',))
                db_schema_version = float(cursor.fetchone()[0] or 0)
            except (TypeError, pymysql.err.ProgrammingError, psycopg.errors.UndefinedTable):
                db_schema_version = 0.000
                if self.db_type == "pgsql":
                    self._conn.commit()

            if db_schema_version < schema_version:
                if self.db_type == "mysql":
                    db_schema = MySQLSchema(self._conn)
                elif self.db_type == "pgsql":
                    db_schema = PgSQLSchema(self._conn)

                if pre_migrate_callback is not None:
                    migration_success = pre_migrate_callback(db_schema_version, cursor)
                    if migration_success == False:
                        self._conn.rollback()
                        return False

                for table_name, table_schema in schema_dict.items():
                    if not db_schema.UpdateTableSchema(table_name, table_schema):
                        return False

                if post_migrate_callback is not None:
                    migration_success = post_migrate_callback(db_schema_version, cursor)
                    if migration_success == False:
                        self._conn.rollback()
                        return False

                if self.db_type == "mysql":
                    sql = "REPLACE cfg_dbase (name, value) VALUES (%s, %s)"
                    cursor.execute(sql, ('schema_version', schema_version))
                elif self.db_type == "pgsql":
                    sql = """
                        INSERT INTO cfg_dbase (name, value)
                             VALUES (%s, %s)
                        ON CONFLICT (name) DO UPDATE
                                SET value = %s
                    """
                    cursor.execute(sql, ('schema_version', schema_version, schema_version))

                self._conn.commit()

        return True
