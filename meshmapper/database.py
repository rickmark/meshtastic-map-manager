import os
import re
import sqlite3

from peewee import *
from yaml import safe_load

from . import ENV_PATH, MODULE_PATH

db = SqliteDatabase(':memory:')

TILE_REGEX = re.compile(r".*/(?P<style>[a-z]+)/(?P<zoom>\d+)/(?P<x>\d+)/(?P<y>\d+)\.png")


class Style(Model):
    id = IntegerField(primary_key=True)
    name = CharField(unique=True)

    class Meta:
        database = db


class Tile(Model):
    id = BigIntegerField(primary_key=True)
    style_id = ForeignKeyField(Style, backref='tiles')
    zoom = IntegerField()
    x = BigIntegerField()
    y = BigIntegerField()
    data = BlobField()

    class Meta:
        database = db

        indexes = (
            # Specify a unique multi-column index on from/to-user.
            (('style_id', 'zoom', 'x', 'y'), True),
        )


class MapDatabase:
    styles = {}

    def __init__(self, filename = None):
        self.filename = filename
        self.db = db
        db.database = filename

    def create_tables(self):
        self.db.create_tables([Style, Tile], safe=True)


    def get_style(self, style_id):
        if style_id not in self.styles:
            result = Style.select().where(Style.name == style_id).execute()
            if result:
                self.styles[style_id] = result[0].id
            else:
                result = Style.create(name=style_id)
                self.styles[style_id] = result.id

        return self.styles[style_id]


    def ingest(self, folder):
        for root, dirs, files in os.walk(folder):
            self.db.savepoint()
            for filename in files:
                fullpath = str(os.path.join(root, filename))
                match = TILE_REGEX.match(fullpath)
                if match is not None:
                    print(f"Ingesting {fullpath}")
                    style, zoom, x, y = match.groups()

                    with open(os.path.join(root, filename), 'rb') as image:
                        data = image.read()

                    style_id = self.get_style(style)
                    result = Tile.select().where(Tile.style_id==style_id, Tile.zoom==int(zoom), Tile.x==int(x), Tile.y==int(y)).execute()
                    if result:
                        result.data = data
                        result.save()
                    else:
                        result = Tile.create(style_id=style_id, zoom=int(zoom), x=int(x), y=int(y), data=data)
                        result.save()
                else:
                    print(f"Skipping {fullpath}")

def main():
    def load_config(config_file: str = "../etc/config.yaml"):
        config_path = os.path.join(MODULE_PATH, config_file)
        return safe_load(open(config_path, "r", encoding="utf-8"))

    config = load_config()
    orm = MapDatabase(os.path.expanduser(config['database']['filename']))
    orm.create_tables()
    orm.ingest(os.path.expanduser(config['database']['flat_files']))
    orm.db.close()