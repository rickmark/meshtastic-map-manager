# Meshtastic Map/tile download script

## Basics
- Download the files in this repo/gist! into a decent folder
- Access that folder on a terminal (cmd or powershell should work but haven't tested out of Linux distros)
- Create your account at https://www.thunderforest.com/docs/apikeys/ (free or paid, up to you)
- Alternatively: can also use https://apidocs.geoapify.com/playground/maps/ (defaults to thunderforest (style atlas))
- Validate your account on your email using received validation link.
- Log in
- Copy API Key from website.
- set API key as env var `API_KEY`
- install needed libraries using `pip install -r requirements.txt`
- Execute main script with `python main.py`
- copy downloaded data into folder `map` at the root of your SD card.
- put your sd card into your T-Deck Plus or favourite Meshtastic device that uses Device-UI.

## tips and extras
- IF IN DOUBT of where data is being written it should be all around the log output but also at the first lines of it.
- If you don't like default directory, must use env var `DOWNLOAD_DIRECTORY` (full path preferably)
- set env var `DEBUG` if you edit this code for it not to download while testing.


### Extras: Tile Sync for your SD.
Added a `synchmaps-config.yaml` example and a `synchmaps.py` to synchronise folders.
It can be done using rsync or other tools but... in GNU/Linux is pretty easy to simply run this multisync defined config... I guess :)

Keep in mind that folders must exist as basic security measure, even if it is an empty folder, to avoid copying things by mistakes like typos :)
