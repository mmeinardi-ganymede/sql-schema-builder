import re
import psycopg


class PgSQLSchema():

    def __init__(self, conn):
        self._conn = conn

    #-----------------------------------------------------------------------------------------------------------

    def _get_table_columns(self, table_name):

        table_columns = None
        with self._conn.cursor() as cursor:
            sql = f"""
                SELECT column_name,
                       data_type, character_maximum_length,
                       column_default,
                       is_nullable, identity_generation
                  FROM INFORMATION_SCHEMA.COLUMNS
                 WHERE table_name = '{table_name}'
            """
            try:
                cursor.execute(sql)
                result = cursor.fetchall()
                table_columns = {}
                for row in result:
                    name = row[0]
                    type = row[1]
                    character_maximum_length = row[2]
                    if character_maximum_length:
                        type = f"{type}({character_maximum_length})"
                    default_value = row[3].split("::", 1)[0].strip("'") if row[3] else None
                    is_notnull = (row[4] == 'NO')
                    is_autoincrement = (row[5] == "ALWAYS")

                    if type.upper().startswith('ENUM('):
                        column_definition = type[:5].upper() + type[5:]
                    else:
                        column_definition = type.upper()
                    if is_autoincrement:
                        column_definition += ' AUTO_INCREMENT'
                    if is_notnull:
                        column_definition += ' NOT NULL'
                    if default_value is not None:
                        column_definition += ' DEFAULT '
                        column_definition += f"'{default_value}'"

                    table_columns[name] = {
                        'column_definition': column_definition,
                        'is_in_primary_key': False,
                    }

            except psycopg.errors.ProgrammingError:
                table_columns = {}

            sql = f"""
                SELECT
                    a.attname
                 FROM
                    pg_class t,
                    pg_class i,
                    pg_index ix,
                    pg_attribute a
                WHERE
                    t.oid = ix.indrelid
                    and i.oid = ix.indexrelid
                    and a.attrelid = t.oid
                    and a.attnum = ANY(ix.indkey)
                    and t.relkind = 'r'
                    and t.relname = '{table_name}'
                    and ix.indisprimary = true
            """

            try:
                cursor.execute(sql)
                for row in cursor.fetchall():
                    column_name = row[0]
                    if column_name in table_columns:
                        table_columns[column_name]['is_in_primary_key'] = True
            except:
                pass

        if table_columns is None:
            raise psycopg.errors.DatabaseError('Cannot get schema for table ' + table_name)

        return table_columns

    #-----------------------------------------------------------------------------------------------------------

    def _get_table_indexes(self, table_name):

        table_indexes = None
        with self._conn.cursor() as cursor:
            sql = f"""
                SELECT
                    i.relname as index_name,
                    ix.indisprimary as is_pk,
                    ix.indisunique as is_unique,
                    array_to_string(array_agg(a.attname), ', ') as column_names
                 FROM
                    pg_class t,
                    pg_class i,
                    pg_index ix,
                    pg_attribute a
                WHERE
                    t.oid = ix.indrelid
                    and i.oid = ix.indexrelid
                    and a.attrelid = t.oid
                    and a.attnum = ANY(ix.indkey)
                    and t.relkind = 'r'
                    and t.relname = '{table_name}'
                GROUP BY
                    index_name, is_pk, is_unique
                ORDER BY
                    index_name
            """

            try:
                cursor.execute(sql)
                result = cursor.fetchall()

                table_indexes = {}
                for row in result:
                    index_name = row[0]
                    is_primary = row[1]
                    is_unique = row[2]

                    type = None
                    if is_primary:
                        type = 'PRIMARY'
                    elif is_unique:
                        type = 'UNIQUE'

                    table_indexes[index_name] = {
                        'type': type,
                        'columns': row[3].split(", ")
                    }

            except:
                table_indexes = {}
        if table_indexes is None:
            raise psycopg.errors.DatabaseError('Cannot get indexes for table ' + table_name)

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
                sql = "CREATE TABLE \"{0}\" ({1})".format(
                    table_name,
                    ','.join('{0} {1}'.format(f['name'], f['column_definition']) for f in sql_fields))
                sql = sql.replace('AUTO_INCREMENT', "GENERATED ALWAYS AS IDENTITY")

                try:
                    cursor.execute(sql)
                except psycopg.errors.ProgrammingError as e:
                    raise

            else:
                for name, metadata in table_columns.items():
                    if name not in [field['name'] for field in sql_fields]:
                        sql = 'ALTER TABLE "{0}" DROP COLUMN {1}'.format(
                            table_name, name)
                        try:
                            cursor.execute(sql)
                        except psycopg.errors.ProgrammingError as e:
                            raise

                for field in sql_fields:
                    if field['name'] not in table_columns:
                        sql = 'ALTER TABLE "{0}" ADD COLUMN {1} {2}'.format(
                            table_name, field['name'], field['column_definition'])
                        sql = sql.replace('AUTO_INCREMENT', "GENERATED ALWAYS AS IDENTITY")
                        try:
                            cursor.execute(sql)
                        except psycopg.errors.ProgrammingError as e:
                            raise
                    else:
                        table_column = table_columns[field['name']]

                        if not self._column_definition_matches(field['column_definition'],
                            table_column['column_definition'],
                            table_column['is_in_primary_key']):

                            column_type = field['column_definition']
                            default_value = None
                            if "DEFAULT" in field['column_definition']:
                                (column_type, default_value) = field['column_definition'].split(" DEFAULT ")

                            sql = 'ALTER TABLE "{0}" ALTER COLUMN {1} TYPE {2}'.format(
                                table_name, field['name'], column_type)

                            is_not_null = "NOT NULL" in field['column_definition']
                            if is_not_null:
                                sql = sql.replace("NOT NULL", "")

                            sql = sql.replace('AUTO_INCREMENT', "")

                            try:
                                cursor.execute(sql)
                                if is_not_null:
                                    sql = 'ALTER TABLE "{0}" ALTER COLUMN {1} SET NOT NULL'.format(
                                        table_name, field['name'])
                                    cursor.execute(sql)
                                if default_value is not None:
                                    sql = 'ALTER TABLE "{0}" ALTER COLUMN {1} SET DEFAULT {2}'.format(
                                        table_name, field['name'], default_value)
                                    cursor.execute(sql)

                            except psycopg.errors.ProgrammingError as e:
                                raise

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

                    sql = f"DROP INDEX {index_name}"
                    try:
                        cursor.execute(sql)
                    except psycopg.errors.ProgrammingError as e:
                        raise

            for index in sql_indexes:
                index_exists = False
                for _, index_schema in table_indexes.items():
                    if index_schema == index:
                        index_exists = True
                        break

                if not index_exists:
                    if index['type'] == 'PRIMARY':
                        sql = 'ALTER TABLE "{0}" {1} ADD PRIMARY KEY ({2})'.format(
                            table_name,
                            ' DROP PRIMARY KEY,' if drop_primary_key_pending else '',
                            ','.join(index['columns']))
                        drop_primary_key_pending = False
                    elif index['type'] == 'UNIQUE':
                        sql = 'ALTER TABLE "{0}" ADD UNIQUE INDEX ({1})'.format(
                            table_name, ','.join(index['columns']))
                    else:
                        sql = 'CREATE INDEX {0}_{2} ON "{0}" ({1})'.format(
                            table_name, ','.join(index['columns']), '_'.join(index['columns']))

                    try:
                        cursor.execute(sql)
                    except psycopg.errors.ProgrammingError as e:
                        raise

            if drop_primary_key_pending:
                sql = 'ALTER TABLE "{0}" DROP PRIMARY KEY'.format(
                    table_name)
                try:
                    cursor.execute(sql)
                except psycopg.errors.ProgrammingError as e:
                    raise

        return True

    #-----------------------------------------------------------------------------------------------------------

    def UpdateTableSchema(self, table_name, schema):

        field_pattern = r'^\s*(\w+)\s+(\w+)(\(([^)]+)\))?(\s+UNSIGNED)?(\s+AUTO_INCREMENT)?(\s+NOTNULL)?(\s+DEFAULT\s+\'?([\w\.]*)\'?)?\s*$'
        index_pattern = r'^\s*INDEX\s+((\w+)\s+)?\(([^\)]+)\)\s*$'

        column_types = {
            'I': 'INTEGER',
            'I1': 'SMALLINT',
            'I2': 'SMALLINT',
            'I8': 'BIGINT',
            'F': 'DOUBLE PRECISION',
            'N': 'DECIMAL(10,2)',

            'C': 'CHARACTER VARYING',
            'MX': 'TEXT',
            'X': 'TEXT',
            'MB': 'BYTEA',
            'B': 'BYTEA',
            'J': 'JSON',
            'BIN': 'BYTEA',

            'D': 'DATE',
            'T': 'TIME',

            'ENUM': 'ENUM',

            'INT8': 'SMALLINT',
            'INT16': 'SMALLINT',
            'INT32': 'INTEGER',
            'INT64': 'BIGINT',
            'CHAR': 'CHARACTER VARYING',
            'DOUBLE': 'DOUBLE PRECISION',
            'TEXT': 'TEXT',
            'BLOB': 'BYTEA',
            'JSON': 'JSON',
            'BOOL': 'BOOLEAN',
            'BOOLEAN': 'BOOLEAN',
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

                sql_indexes.append({'type': index_type, 'columns': ['{}'.format(x.strip()) for x in index_fields.split(',')] })
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
            if type in ['C', 'CHAR'] and not type_arguments:
                raise ValueError('Char type requires size: ' + field)
            if type == 'ENUM' and not type_arguments:
                raise ValueError('Enum type requires list of possible values: ' + field)
            if type == 'BIN' and not type_arguments:
                raise ValueError('Binary type requires size: ' + field)
            if type not in ['C', 'CHAR', 'ENUM', 'BIN'] and type_arguments:
                raise ValueError('Only char or enum type can have arguments: ' + field)

            column_definition = column_types[type]
            if type in ['C', 'CHAR', 'ENUM']:
                if type == 'ENUM':
                    # Strip whitespace between enum values for canonical form.
                    type_arguments = ','.join("'{}'".format(x) for x in re.findall(r"'([^']*?)'", type_arguments))
                    # We don't support ENUM type for PostgreSQL yet. We convert it to CHAR.
                    column_definition = column_types["CHAR"]
                    type_arguments = max([len(x) for x in type_arguments.split(",")] or [1])
                column_definition += '({0})'.format(type_arguments)
            elif type == 'BIN':
                # We ignore size specifier for BIN column on PostgreSQL.
                pass
            if is_unsigned:
                column_definition += ' UNSIGNED'
            if is_autoincrement:
                column_definition += ' AUTO_INCREMENT'
            if is_notnull:
                column_definition += ' NOT NULL'
            if default_value is not None:
                column_definition += ' DEFAULT '
                column_definition += f"'{default_value}'"

            sql_fields.append({'name': name, 'column_definition': column_definition})

        if not self._update_table_columns(table_name, sql_fields):
            return False
        if not self._update_table_indexes(table_name, sql_indexes):
            return False

        return True
