import re
import pymysql


class MySQLSchema():

    def __init__(self, conn):
        self._conn = conn

    #-----------------------------------------------------------------------------------------------------------

    def _get_table_columns(self, table_name):

        table_columns = None
        with self._conn.cursor() as cursor:
            sql = "SHOW COLUMNS FROM {0}".format(table_name)
            try:
                cursor.execute(sql)
                result = cursor.fetchall()
                table_columns = {}
                prev_name = None
                for row in result:
                    name = row[0]
                    type = row[1]
                    is_notnull = (row[2] == 'NO')
                    is_in_primary_key = (row[3] == 'PRI')
                    default_value = row[4]
                    is_autoincrement = (row[5] == 'auto_increment')

                    column_definition = type.upper()
                    if is_autoincrement:
                        column_definition += ' AUTO_INCREMENT'
                    if is_notnull:
                        column_definition += ' NOT NULL'
                    if default_value is not None:
                        column_definition += ' DEFAULT '
                        column_definition += self._conn.escape(str(default_value))

                    table_columns[name] = {
                        'column_definition': column_definition,
                        'is_in_primary_key': is_in_primary_key,
                        'prev_name': prev_name
                    }
                    prev_name = name

            except pymysql.err.ProgrammingError as e:
                if e.args[0] == pymysql.constants.ER.NO_SUCH_TABLE:
                    table_columns = {}
        if table_columns is None:
            raise pymysql.err.DatabaseError('Cannot get schema for table ' + table_name)

        return table_columns

    #-----------------------------------------------------------------------------------------------------------

    def _get_table_indexes(self, table_name):

        table_indexes = None
        with self._conn.cursor() as cursor:
            sql = "SHOW INDEXES FROM {0}".format(table_name)
            try:
                cursor.execute(sql)
                result = cursor.fetchall()
                table_indexes = {}
                for row in result:
                    non_unique = row[1]
                    index_name = row[2]
                    seq_in_index = row[3]
                    column_name = '`{0}`'.format(row[4])

                    type = None
                    if index_name == 'PRIMARY':
                        type = 'PRIMARY'
                    elif non_unique == 0:
                        type = 'UNIQUE'

                    if index_name not in table_indexes:
                        table_indexes[index_name] = { 'columns': [] }

                    table_indexes[index_name]['type'] = type
                    while len(table_indexes[index_name]['columns']) < seq_in_index:
                        table_indexes[index_name]['columns'].append('')
                    table_indexes[index_name]['columns'][seq_in_index - 1] = column_name

            except pymysql.err.ProgrammingError as e:
                if e.args[0] == pymysql.constants.ER.NO_SUCH_TABLE:
                    table_indexes = {}
        if table_indexes is None:
            raise pymysql.err.DatabaseError('Cannot get indexes for table ' + table_name)

        return table_indexes

    #-----------------------------------------------------------------------------------------------------------

    def _column_definition_matches(self, sql_field_definition, table_column_definition, is_in_primary_key):
        current_column_definition = table_column_definition
        if sql_field_definition == current_column_definition:
            return True

        # MySQL implicitly adds NOT NULL/DEFAULT to columns in PRIMARY KEY.
        if is_in_primary_key:
            current_column_definition = current_column_definition.replace(' NOT NULL', '')
            if sql_field_definition == current_column_definition:
                return True
            idx = current_column_definition.find(' DEFAULT')
            if idx > 0:
                current_column_definition = current_column_definition[:idx]
                if sql_field_definition == current_column_definition:
                    return True

        return False

    def _update_table_columns(self, table_name, sql_fields):

        table_columns = self._get_table_columns(table_name)

        with self._conn.cursor() as cursor:
            if len(table_columns) == 0:
                sql = "CREATE TABLE {0} ({1})".format(
                    table_name,
                    ','.join('`{0}` {1}'.format(f['name'], f['column_definition']) for f in sql_fields))
                sql = sql.replace('AUTO_INCREMENT', '')
                try:
                    cursor.execute(sql)
                except pymysql.err.ProgrammingError as e:
                    raise

            else:
                for name, metadata in table_columns.items():
                    if name not in [field['name'] for field in sql_fields]:
                        sql = 'ALTER TABLE {0} DROP COLUMN `{1}`'.format(
                            table_name, name)
                        try:
                            cursor.execute(sql)
                        except pymysql.err.ProgrammingError as e:
                            raise

                prev_field_name = None
                for field in sql_fields:
                    if field['name'] not in table_columns:
                        sql = 'ALTER TABLE {0} ADD COLUMN `{1}` {2} {3}'.format(
                            table_name, field['name'], field['column_definition'],
                            'FIRST' if prev_field_name is None else 'AFTER {0}'.format(prev_field_name))
                        try:
                            cursor.execute(sql)
                        except pymysql.err.ProgrammingError as e:
                            raise
                    else:
                        table_column = table_columns[field['name']]

                        if not self._column_definition_matches(field['column_definition'],
                            table_column['column_definition'],
                            table_column['is_in_primary_key']) or \
                            prev_field_name != table_column['prev_name']:

                            sql = 'ALTER TABLE {0} CHANGE COLUMN `{1}` `{2}` {3} {4}'.format(
                                table_name, field['name'], field['name'], field['column_definition'],
                                'FIRST' if prev_field_name is None else 'AFTER {0}'.format(prev_field_name))
                            try:
                                cursor.execute(sql)
                            except pymysql.err.ProgrammingError as e:
                                raise

                    prev_field_name = field['name']

        return True

    #-----------------------------------------------------------------------------------------------------------

    def _update_table_indexes(self, table_name, sql_indexes):

        table_indexes = self._get_table_indexes(table_name)

        with self._conn.cursor() as cursor:

            drop_primary_key_pending = False

            for index_name, index_schema in table_indexes.items():
                if index_schema not in sql_indexes:
                    if index_schema['type'] == 'PRIMARY':
                        drop_primary_key_pending = True
                        continue

                    sql = 'ALTER TABLE {0} DROP INDEX {1}'.format(
                        table_name, index_name)
                    try:
                        cursor.execute(sql)
                    except pymysql.err.ProgrammingError as e:
                        raise

            for index in sql_indexes:
                index_exists = False
                for _, index_schema in table_indexes.items():
                    if index_schema == index:
                        index_exists = True
                        break
                if not index_exists:
                    if index['type'] == 'PRIMARY':
                        sql = 'ALTER TABLE {0} {1} ADD PRIMARY KEY ({2})'.format(
                            table_name,
                            ' DROP PRIMARY KEY,' if drop_primary_key_pending else '',
                            ','.join(index['columns']))
                        drop_primary_key_pending = False
                    elif index['type'] == 'UNIQUE':
                        sql = 'ALTER TABLE {0} ADD UNIQUE INDEX ({1})'.format(
                            table_name, ','.join(index['columns']))
                    else:
                        sql = 'ALTER TABLE {0} ADD INDEX ({1})'.format(
                            table_name, ','.join(index['columns']))

                    try:
                        cursor.execute(sql)
                    except pymysql.err.ProgrammingError as e:
                        raise

            if drop_primary_key_pending:
                sql = 'ALTER TABLE {0} DROP PRIMARY KEY'.format(
                    table_name)
                try:
                    cursor.execute(sql)
                except pymysql.err.ProgrammingError as e:
                    raise

        return True

    #-----------------------------------------------------------------------------------------------------------

    def UpdateTableSchema(self, table_name, schema):

        field_pattern = r'^\s*(\w+)\s+(\w+)(\(([^)]+)\))?(\s+UNSIGNED)?(\s+AUTO_INCREMENT)?(\s+NOTNULL)?(\s+DEFAULT\s+\'?(\w*)\'?)?\s*$'
        index_pattern = r'^\s*INDEX\s+((\w+)\s+)?\(([^\)]+)\)\s*$'

        column_types = {
            'I': 'INT(11)',
            'I1': 'TINYINT(4)',
            'I2': 'SMALLINT(6)',
            'I8': 'BIGINT(20)',
            'F': 'DOUBLE',
            'N': 'DECIMAL(10,2)',

            'C': 'VARCHAR',
            'MX': 'MEDIUMTEXT',
            'X': 'LONGTEXT',
            'MB': 'MEDIUMBLOB',
            'B': 'LONGBLOB',
            'J': 'JSON',
            'BIN': 'BINARY',

            'D': 'DATE',
            'T': 'DATETIME',

            'ENUM': 'ENUM',
        }

        fields = [x.strip() if not x.strip().endswith(',') else x.strip()[:-1].strip() for x in schema.splitlines()]

        sql_fields = []
        sql_indexes = []
        for field in fields:
            if len(field) == 0:
                continue
            matches = re.match(field_pattern, field)
            if not matches:
                matches = re.match(index_pattern, field)
                if not matches:
                    raise ValueError('Invalid field specifier: ' + field)

                index_type = matches.group(2)
                index_fields = matches.group(3)
                if index_type not in (None, 'PRIMARY', 'UNIQUE'):
                    raise ValueError('Invalid index type: ' + field)

                sql_indexes.append({'type': index_type, 'columns': ['`{}`'.format(x.strip()) for x in index_fields.split(',')] })
                continue

            name = matches.group(1)
            type = matches.group(2)
            type_arguments = matches.group(4)
            is_unsigned = matches.group(5) is not None
            is_autoincrement = matches.group(6) is not None
            is_notnull = matches.group(7) is not None
            default_value = matches.group(9)

            if type not in column_types:
                raise ValueError('Invalid type specifier: ' + field)
            if type == 'C' and not type_arguments:
                raise ValueError('Char type requires size: ' + field)
            if type == 'ENUM' and not type_arguments:
                raise ValueError('Enum type requires list of possible values: ' + field)
            if type == 'BIN' and not type_arguments:
                raise ValueError('Binary type requires size: ' + field)
            if type not in ['C', 'ENUM', 'BIN'] and type_arguments:
                raise ValueError('Only char or enum type can have arguments: ' + field)

            column_definition = column_types[type]
            if type in ['C', 'ENUM', 'BIN']:
                column_definition += '({0})'.format(type_arguments)
            if is_unsigned:
                column_definition += ' UNSIGNED'
            if is_autoincrement:
                column_definition += ' AUTO_INCREMENT'
            if is_notnull:
                column_definition += ' NOT NULL'
            if default_value is not None:
                column_definition += ' DEFAULT '
                column_definition += self._conn.escape(str(default_value))

            sql_fields.append({'name': name, 'column_definition': column_definition})

        if not self._update_table_columns(table_name, sql_fields):
            return False
        if not self._update_table_indexes(table_name, sql_indexes):
            return False
        # AUTO_INCREMENT can be set only after primary index is created.
        if any('AUTO_INCREMENT' in f['column_definition'] for f in sql_fields):
            if not self._update_table_columns(table_name, sql_fields):
                return False

        return True
