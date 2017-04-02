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

db_schema = SQLSchemaBuilder(host='localhost', user='root', passwd='xxx', db='premierleague')
db_schema.UpdateSchema(*_get_schema())
