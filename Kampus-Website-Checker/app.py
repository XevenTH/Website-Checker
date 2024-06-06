from flask import Flask, jsonify, render_template
import asyncio
import aiohttp
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import atexit
import logging
import json

logging.basicConfig(level=logging.INFO)
app = Flask(__name__, template_folder='WWW', static_folder='Data')


def ReadJSON(path):
    with open(path, 'r') as jsonFile:
        data = json.load(jsonFile)
    return data


jsonFile = 'Data/kampus.json'
data = ReadJSON(jsonFile)
urls = {dataWeb['url']: 'UNKNOWN' for dataWeb in data['data']}

statusObj = {}


async def ReadStatus(session, url):
    try:
        async with session.get(url, timeout=20, allow_redirects=False) as response:
            if response.status == 200:
                return url, 'UP'
            elif 300 <= response.status < 400:
                return url, 'REDIRECTED'
            else:
                return url, 'DOWN'
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return url, 'UNKNOWN'
    except Exception as e:
        logging.error(f"Error checking {url}: {e}")
        return url, 'DOWN'


async def CekWebStatus(url_group):
    async with aiohttp.ClientSession() as session:
        tasks = [ReadStatus(session, url) for url in url_group]
        results = await asyncio.gather(*tasks)
        for url, status in results:
            statusObj[url] = status


def ScheduleChecks():
    up_urls = [url for url, status in statusObj.items()
               if status == 'UP']
    down_urls = [url for url, status in statusObj.items()
                 if status == 'DOWN']
    unknown_urls = [url for url, status in statusObj.items()
                    if status == 'UNKNOWN']
    redirect_urls = [url for url, status in statusObj.items()
                     if status == 'REDIRECTED']

    asyncio.run(CekWebStatus(up_urls))
    asyncio.run(CekWebStatus(down_urls))
    asyncio.run(CekWebStatus(unknown_urls))
    asyncio.run(CekWebStatus(redirect_urls))


scheduler = BackgroundScheduler(timezone=pytz.utc)
scheduler.add_job(func=lambda: asyncio.run(
    CekWebStatus(urls.keys())), trigger="interval", seconds=60)
scheduler.add_job(func=lambda: ScheduleChecks(),
                  trigger="interval", seconds=10)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())


@app.route('/api/website', methods=['GET'])
def get_websites():
    return jsonify(data)


@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(statusObj)


@app.route('/')
def index():
    return render_template('app.html')


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(CekWebStatus(urls.keys()))
    loop.close()
    app.run(host='0.0.0.0', port=11006)
