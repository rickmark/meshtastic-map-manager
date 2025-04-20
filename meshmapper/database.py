import os
import re
import sqlite3

from typing import Optional
from peewee import *
from yaml import safe_load

from . import MODULE_PATH

db = SqliteDatabase(':memory:')

TILE_REGEX = re.compile(r".*/(?P<style>[a-z]+)/(?P<zoom>\d+)/(?P<x>\d+)/(?P<y>\d+)\.png")


class Metadata(Model):
    name = TextField()
    value = TextField()

    class Meta:
        id = IntegerField(primary_key=True)
        database = db
        db_table = 'metadata'


class Tile(Model):
    id = BigIntegerField(primary_key=True)
    zoom_level = IntegerField()
    tile_column = IntegerField()
    tile_row = IntegerField()
    tile_data = BlobField()

    class Meta:
        database = db
        db_table = 'tiles'

class MapDatabase:
    styles = {}

    def __init__(self, filename = None):
        self.filename = filename
        self.db = db
        db.database = filename

    def create_tables(self):
        self.db.create_tables([Metadata, Tile], safe=True)
        Tile.add_index(Tile.zoom_level, Tile.tile_column, Tile.tile_row, unique=True, name='tile_index')

    @staticmethod
    def get_setting(name) -> Optional[str]:
        result = Metadata.get_or_none(Metadata.name == name)
        if result is not None:
            return result.value
        return None

    @staticmethod
    def set_setting(name, value):
        result = Metadata.get_or_none(Metadata.name == name)
        if result is not None:
            result.value = value
            result.save()
        else:
            Metadata.create(name=name, value=value)

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

                    result = Tile.select().where(Tile.zoom_level==int(zoom), Tile.tile_column==int(x), Tile.tile_row==int(y)).execute()
                    if result:
                        result.data = data
                        result.save()
                    else:
                        result = Tile.create(zoom_level=int(zoom), tile_column=int(x), tile_row=int(y), tile_data=data)
                        result.save()
                else:
                    print(f"Skipping {fullpath}")

def main():
    def load_config(config_file: str = "../etc/config.yaml"):
        config_path = os.path.join(MODULE_PATH, config_file)
        return safe_load(open(config_path, "r", encoding="utf-8"))

    for style, config in load_config()['database'].items():
        orm = MapDatabase(os.path.expanduser(config['filename']))
        orm.create_tables()
        orm.set_setting('name', f"{style}.db")
        orm.set_setting('format', 'png')
        orm.ingest(os.path.expanduser(config['flat_files']))
        orm.db.close()