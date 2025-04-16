import os
import pathlib
import shutil
from os import PathLike

from yaml import safe_load
from os.path import isdir, expanduser, isfile, join
from time import sleep

MODULE_PATH = os.path.dirname(__file__)


class FolderSync:
    destination: PathLike[str]

    def __init__(self, source, destination):
        """
        Initializes the FolderSync instance.
        :param source: Source directory path.
        :param destination: Destination directory path.
        """
        self.source = source
        self.destination = destination

    def verify_main_folders_exist(self):
        if not isdir(self.source):
            self.print(f"Source path '{self.source}' does not exist.")
            return False
        if not isdir(self.destination):
            self.print(f"Destination folder '{self.destination}' must exist already even if it is empty.")
            return False
        return True

    def sync(self):
        """
        Synchronizes files from source to destination without overwriting existing ones.
        """
        if not self.verify_main_folders_exist():
            return False

        for root, dirs, files in os.walk(self.source):
            relative_path = pathlib.Path(root).relative_to(self.source)
            dest_path = self.destination / relative_path if relative_path != "." else pathlib.Path(self.destination)

            if not isdir(dest_path):
                self.print(f"Creating dir: {dest_path}")
                os.makedirs(dest_path)

            for file in files:
                src_file = pathlib.Path(root) / file
                dest_file = dest_path / file

                if not isfile(dest_file):  # Only copy if missing
                    self.print(f"Copying missing file to {dest_file}")
                    shutil.copy2(src_file, dest_file)  # copy2 preserves metadata
        return True

    def print(self, message: str):
        print(f"[Sync] {self.source} → {self.destination}: {message}")


def main():
    config_file = join(MODULE_PATH, "../etc/synchmaps-config.yaml")
    print(f"[Sync] Configuration file: {config_file}")
    config = safe_load(open(config_file, "r", encoding="utf-8"))

    failed_syncs = 0
    success_syncs = 0
    for sync in config['sync']:
        unit_source = expanduser(sync['source'])
        unit_destination = expanduser(sync['destination'])
        syncer = FolderSync(unit_source, unit_destination)
        syncer.print("validating folders")
        if syncer.verify_main_folders_exist():
            syncer.print("Will start in 3 seconds...")
            sleep(3)
            if not syncer.sync():
                syncer.print("Sync failed.")
                failed_syncs += 1
            else:
                syncer.print("Sync completed.")
                success_syncs += 1
        else:
            syncer.print("Sync failed.")
            failed_syncs += 1

    print(f"Total syncs:\n\t[failed/aborted]: {failed_syncs}\n\t[succeeded]: {success_syncs}")
