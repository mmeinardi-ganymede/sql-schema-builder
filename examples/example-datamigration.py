import pymysql
from sql_schema_builder.SQLSchemaBuilder import SQLSchemaBuilder

# Database which schema we control.
class DatabasePremierLeague():

    @classmethod
    def _get_schema(cls):

        schema = {}
        schema_version = 1.020

        schema['teams'] = """
            id_team I NOTNULL DEFAULT 0,
            name C(32),

            points I,
            matches_won I,
            matches_drawn I,
            matches_lost I,

            total_goals I,

            coach_name C(64),

            timestamp_updated I8,
            INDEX PRIMARY (id_team),
            INDEX (timestamp_updated)
        """

        schema['players'] = """
            id_player I NOTNULL DEFAULT 0,
            name C(64),
            id_team I,

            shirt_number I,
            position ENUM('', 'goalkeeper', 'defender', 'midfielder', 'forward') DEFAULT '',

            goals_scored I,

            height I,
            weight F,

            INDEX PRIMARY (id_player),
            INDEX (id_team, id_player)
        """

        return schema, schema_version

    @classmethod
    def _migrate_schema(cls, db_schema_version, cursor):

        if db_schema_version < 1.020:
            sql = """SELECT id_team, SUM(goals_scored) FROM players GROUP BY id_team"""
            cursor.execute(sql)
            rows = cursor.fetchall()
            for row in rows:
                sql = """UPDATE teams SET total_goals = %s WHERE id_team = %s AND total_goals IS NULL"""
                cursor.execute(sql, (row[1], row[0]))


conn = pymysql.connect(host='localhost', user='root', passwd='xxx', db='premierleague')
db_schema = SQLSchemaBuilder(pymysql_conn=conn)
db_schema.UpdateSchema(*DatabasePremierLeague._get_schema(), post_migrate_callback=DatabasePremierLeague._migrate_schema)
