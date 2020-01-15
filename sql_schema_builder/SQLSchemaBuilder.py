from sql_schema_builder.MySQLSchema import MySQLSchema
import pymysql


class SQLSchemaBuilder:

    def __init__(self, host=None, port=3306, user=None, passwd=None, db=None, pymysql_conn=None, create_db=False):
        self._conn = None
        self._conn_params = {}

        if pymysql_conn is not None:
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
            self._conn.select_db(db)

    def _create_database(self, db_name):
        self._connect_to_database()
        if self._conn is None:
            return False

        try:
            with self._conn.cursor() as cursor:
                try:
                    sql = "SHOW DATABASES LIKE %s"
                    cursor.execute(sql, (db_name,))
                    if cursor.fetchone() is None:
                        sql = "CREATE DATABASE IF NOT EXISTS `{}`".format(db_name)
                        cursor.execute(sql)
                except Exception as e:
                    pass
        except Exception as e:
            pass

    def _connect_to_database(self):

        if self._conn is not None:
            return self._conn

        try:
            self._conn = pymysql.connect(
                host=self._conn_params['host'],
                port=self._conn_params['port'],
                user=self._conn_params['user'],
                passwd=self._conn_params['passwd'],
                db=self._conn_params['db'],
                charset = 'utf8',
                autocommit=False)
        except pymysql.err.DatabaseError:
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
            except (TypeError, pymysql.err.ProgrammingError):
                db_schema_version = 0.000

            if db_schema_version < schema_version:
                mysql_schema = MySQLSchema(self._conn)

                if pre_migrate_callback is not None:
                    migration_success = pre_migrate_callback(db_schema_version, cursor)
                    if migration_success == False:
                        self._conn.rollback()
                        return False

                for table_name, table_schema in schema_dict.items():
                    if not mysql_schema.UpdateTableSchema(table_name, table_schema):
                        return False

                if post_migrate_callback is not None:
                    migration_success = post_migrate_callback(db_schema_version, cursor)
                    if migration_success == False:
                        self._conn.rollback()
                        return False

                sql = "REPLACE cfg_dbase (name, value) VALUES (%s, %s)"
                cursor.execute(sql, ('schema_version', schema_version))

                self._conn.commit()

        return True
