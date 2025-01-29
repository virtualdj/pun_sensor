""" Test that the data can be retrieved """

import aiohttp
import asyncio
import logging
import json
import os
import sys
from zoneinfo import ZoneInfo

# Load parent folder as library
sys.path.append(os.path.abspath('..'))
from lib.data_downloader import DataDownloader

async def main():
    logger = logging.getLogger(__name__)
    tz_pun = ZoneInfo("Europe/Rome")

    # Use DataDownloader directly to fetch data
    async with aiohttp.ClientSession() as session:
        downloader = DataDownloader(logger, session)
        await downloader.get(tz_pun)
        # Dump the `pun_orari` structure as JSON to stdout
        print(json.dumps(downloader.pun_data.pun_orari))

# Start asyncio loop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
asyncio.run(main())
