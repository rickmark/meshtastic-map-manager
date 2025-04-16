import asyncio
import dataclasses
import logging
import os
from concurrent.futures import as_completed
from io import BytesIO
from os import environ, makedirs
from math import floor, pi, tan, cos, log
from os.path import join as join_path, expanduser, exists
from sys import exit
from typing import Iterator
import concurrent.futures
from PIL import Image
from dotenv import load_dotenv
from requests import get
from tqdm import tqdm
from yaml import safe_load

'''
Authors:
  - DRoBeR (Meshtastic Spain community)
  - pcamelo (Meshtastic Portugal community)
  - Find us via LoRa Channel: Iberia. (or Telegram communities)
  - UPDATES at: https://gist.github.com/droberin/b333a216d860361e329e74f59f4af4ba
  - Thunderforest info: Maps © www.thunderforest.com, Data © www.osm.org/copyright

Providers (TODO: organise and add proper credits!):
You need an API key from a valid account from https://www.thunderforest.com/docs/apikeys/ or other valid provider
They offer them for free for hobbies projects. DO NOT ABUSE IT!
This script would try to avoid downloading existing files to protec their service and your own account.

Don't forge to check: https://www.openstreetmap.org/copyright

Base code from: Tile downloader https://github.com/fistulareffigy/MTD-Script/blob/main/TileDL.py
'''

MODULE_PATH = os.path.dirname(__file__)
ENV_PATH = os.path.join(MODULE_PATH, '../.env')

@dataclasses.dataclass
class Tile:
    x: int
    y: int
    zoom: int

class MeshtasticTileDownloader:
    def __init__(self, output_directory: str):
        self.config = None
        self.output_directory = output_directory
        if not self.load_config():
            logging.critical("Configuration was not properly obtained from file.")

    @property
    def tile_provider(self):
        return self.config['map']['provider']

    @tile_provider.setter
    def tile_provider(self, provider):
        if provider in self.known_providers:
            self.config['map']['provider'] = provider
        else:
            logging.warning(f"Known providers: {self.known_providers}")
            raise ValueError(f"Unknown provider: {provider}")

    @property
    def known_providers(self):
        return [x for x in self.get_tile_provider_url_template().keys()]

    @property
    def map_style(self):
        return self.config.get("map").get("style")

    @map_style.setter
    def map_style(self, style):
        self.config['map']['style'] = style

    @property
    def api_key(self):
        return self.config['api_key']

    @api_key.setter
    def api_key(self, key):
        self.config['api_key'] = key

    @property
    def zones(self):
        return [x for x in self.config['zones']]

    def load_config(self, config_file: str = "../etc/config.yaml"):
        config_path = join_path(MODULE_PATH, config_file)
        self.config = safe_load(open(config_path, "r", encoding="utf-8"))
        return self.config

    def validate_config(self):
        logging.info("Analysing configuration.")
        try:
            fixing_zone = self.config['zones']
            logging.info(f"Found {len(fixing_zone)} zones")
            for zone in fixing_zone:
                regions = fixing_zone[zone]['regions']
                logging.info(f"[{zone}] contains {len(regions)} regions")
                if 'zoom' not in fixing_zone[zone]:
                    logging.debug("no zoom defined. will set to default zoom")
                    fixing_zone[zone]['zoom'] = {}
                if 'in' not in fixing_zone[zone]['zoom']:
                    fixing_zone[zone]['zoom']['in'] = 8
                if 'out' not in fixing_zone[zone]['zoom']:
                    fixing_zone[zone]['zoom']['out'] = 1
            if 'map' not in self.config:
                self.config['map'] = {
                    'provider': "thunderforest",
                    'style': "atlas",
                    'reduce': 12
                }
            if 'provider' not in self.config['map']:
                self.config['map']['provider'] = "thunderforest"
            if 'style' not in self.config['map']:
                self.config['map']['style'] = "atlas"
            if 'reduce' not in self.config['map']:
                self.config['map']['reduce'] = 12
            elif self.config['map']['reduce'] < 1 or self.config['map']['reduce'] > 16:
                self.config['map']['reduce'] = 100
            if not self.is_valid_provider:
                known_ones = ", ".join(self.known_providers)
                logging.critical(f"Provider '{self.tile_provider}' is unknown. Known: '{known_ones}'")
                return False
        except KeyError as e:
            logging.error(f"Error found on config. key not found: {e}")
            return False
        return True

    @staticmethod
    def in_debug_mode():
        return environ.get("DEBUG", "false")



    @staticmethod
    def load_image_bytes(image_bytes):
        # if it has alpha channel it gets removed
        img = Image.open(BytesIO(image_bytes))
        if img.has_transparency_data:
            return img.convert("RGB")
        return img

    @staticmethod
    def convert_png_to_256_colors(image):
        """
        Loads a PNG file, converts it to 256 colors with 8-bit depth, and removes background alpha.
        :param image: PNG bytes.
        :return: Modified PIL Image object.
        """
        return image.quantize(colors=256, method=2)

    def reduce_tile(self, image_bytes, destination):
        image = self.convert_png_to_256_colors(image_bytes)
        self.save_tile_file(image, destination)

    @staticmethod
    def save_tile_file(image_bytes, destination):
        return image_bytes.save(destination, format="PNG", optimize=True)

    @property
    def is_valid_provider(self):
        return self.tile_provider in self.get_tile_provider_url_template()

    @staticmethod
    def get_tile_provider_url_template():
        # Do we need jinja2 for this? overkill?
        return {
            "thunderforest": 'https://tile.thunderforest.com/{{MAP_STYLE}}/{{ZOOM}}/{{X}}/{{Y}}.png?apikey={{API_KEY}}',
            "geoapify": 'https://maps.geoapify.com/v1/tile/{{MAP_STYLE}}/{{ZOOM}}/{{X}}/{{Y}}.png?apiKey={{API_KEY}}',
            "cnig.es": 'https://tms-ign-base.idee.es/1.0.0/IGNBaseTodo/{{ZOOM}}/{{X}}/{{Y}}.jpeg',
            "USGS": 'https://basemap.nationalmap.gov/arcgis/rest/services/{{MAP_STYLE}}/MapServer/tile/{{ZOOM}}/{{Y}}/{{X}}',
            "ESRI": 'https://services.arcgisonline.com/ArcGIS/rest/services/{{MAP_STYLE}}/MapServer/tile/{{ZOOM}}/{{X}}/{{Y}}'
        }

    def parse_url(self, zoom: int, x: int, y: int):
        url = self.get_tile_provider_url_template().get(self.tile_provider)
        return str(url).replace(
            "{{MAP_STYLE}}", self.map_style
        ).replace(
            "{{ZOOM}}", str(zoom)
        ).replace(
            "{{X}}", str(x)
        ).replace(
            "{{Y}}", str(y)
        ).replace(
            "{{API_KEY}}", self.api_key
        )

    def redact_key(self, url: str):
        return url.replace(self.api_key, '[REDACTED]')

    def download_tile(self, zoom, x, y):
        reducing = zoom >= self.config['map']['reduce']
        url = self.parse_url(zoom, x, y)
        redacted_url = self.redact_key(url)
        tile_dir = join_path(self.output_directory, self.tile_provider, self.map_style, str(zoom), str(x))
        tile_path = join_path(tile_dir, f"{y}.png")
        makedirs(tile_dir, exist_ok=True)
        if exists(tile_path):
            try:
                img = Image.open(tile_path)
                img.verify()
            except Exception as e:
                os.remove(tile_path)
        if not exists(tile_path):
            if self.in_debug_mode().lower() != "false":
                logging.warning(f"DEBUG IS ACTIVE: not obtaining tile: {redacted_url} (Would reduce: {reducing})")
                return False
            response = get(url)
            if response.status_code == 200:
                content_type = response.headers["content-type"]
                if not str(content_type).startswith("image/"):
                    logging.error(f"Failed to parse tile {zoom}/{x}/{y}: {response.status_code}: not an image.")
                if reducing:
                    logging.debug(f"Reducing tile from {redacted_url} → {tile_path}")
                    self.reduce_tile(
                        self.load_image_bytes(response.content),
                        tile_path
                    )
                else:
                    if content_type != "image/png":
                        logging.debug(f"[Tile type: {content_type}] Saving tile as PNG instead {redacted_url} → {tile_path}")
                        self.save_tile_file(self.load_image_bytes(response.content), tile_path)
                    else:
                        logging.debug(f"Saving not altered tile {redacted_url} → {tile_path}")
                        with open(tile_path, "wb") as file:
                            file.write(response.content)
            else:
                logging.error(f"Failed to download tile {zoom}/{x}/{y}: {response.status_code} {response.reason}")
        else:
            logging.debug(f"[{tile_path}] file already exists. Skipping... {redacted_url}")

    @staticmethod
    def long_to_tile_x(lon: float, zoom: int) -> int:
        xy_tiles_count = 2 ** zoom
        return int(floor(((lon + 180.0) / 360.0) * xy_tiles_count))

    @staticmethod
    def lat_to_tile_y(lat: float, zoom: int) -> int:
        xy_tiles_count = 2 ** zoom
        return int(floor(((1.0 - log(tan((lat * pi) / 180.0) + 1.0 / cos(
            (lat * pi) / 180.0)) / pi) / 2.0) * xy_tiles_count))

    # renamed from main
    async def obtain_tiles(self, regions: list, zoom_levels: range) -> None:
        tiles = [
            tile
            for zoom in zoom_levels
            for region in regions
            for tile in self.tiles_in(region, zoom)
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=128) as executor:
            futures = [
                executor.submit(self.download_tile, tile.zoom, tile.x, tile.y)
                for tile in tiles
            ]

            with tqdm(total=len(tiles), desc="Downloading tiles") as pbar:
                for future in as_completed(futures):
                    pbar.update(1)



    def tiles_in(self, region: str, zoom: int) -> Iterator[Tile]:
        min_lat, min_lon, max_lat, max_lon = list(map(float, region.split(",")))
        start_x = self.long_to_tile_x(min_lon, zoom)
        end_x = self.long_to_tile_x(max_lon, zoom)
        start_y = self.lat_to_tile_y(max_lat, zoom)
        end_y = self.lat_to_tile_y(min_lat, zoom)

        for x in range(min(start_x, end_x), max(start_x, end_x) + 1):
            for y in range(min(start_y, end_y), max(start_y, end_y) + 1):
                yield Tile(x, y, zoom)

    async def run(self) -> bool:
        if not self.is_valid_provider:
            logging.critical(f"Unknown provider '{self.tile_provider}'")
            return False
        processing_zone = self.config['zones']
        for zone in processing_zone:
            regions = processing_zone[zone]['regions']
            zoom_out = processing_zone[zone]['zoom']['out']
            zoom_in = processing_zone[zone]['zoom']['in']
            zoom_levels = range(zoom_out, zoom_in)
            logging.info(f"Obtaining zone [{zone}] [zoom: {zoom_out} → {zoom_in}] regions: {regions}")
            await self.obtain_tiles(regions=regions, zoom_levels=zoom_levels)
            logging.info(f"Finished with zone {zone}")
        zones = ", ".join(self.zones)
        logging.info(f"Finished processing zones: {zones}")
        return True


async def do():
    if exists(ENV_PATH):
        load_dotenv()
    if str(environ.get("DEBUG", "false")).lower() == "true":
        logging.basicConfig(level=logging.DEBUG)
        logging.warning("Log level is set to DEBUG")
    else:
        logging.basicConfig(level=logging.INFO)

    # API Key and output directory
    output_dir = environ.get("DOWNLOAD_DIRECTORY", join_path(expanduser("~"), "Desktop", "maps"))
    makedirs(output_dir, exist_ok=True)
    if not exists(output_dir):
        logging.critical(f"Destination '{output_dir}' can't be created. (use env var DOWNLOAD_DIRECTORY")
        exit(2)
    logging.info(f"Store destination set at: {output_dir}")
    app = MeshtasticTileDownloader(output_directory=output_dir)

    if not app.validate_config():
        logging.critical("Configuration is not valid.")
        exit(1)

    provider_env_var = str(app.tile_provider + "_API_KEY").upper()
    app.api_key = environ.get(provider_env_var, environ.get("API_KEY", None))
    if not app.api_key:
        logging.critical(f"Neither API_KEY env var or PROVIDER_API_KEY (ex: {provider_env_var}) found")
        logging.info("If your provider doesn't need an API Key, set the env var with any content.")
        exit(1)

    if not await app.run():
        logging.info("Program finished with errors.")
        exit(1)

    logging.info("Program finished")
    exit(0)

def main():
    asyncio.run(do())