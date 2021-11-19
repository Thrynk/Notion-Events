from notion.client import NotionClient
import os
from time import sleep
import logging

logging.basicConfig(filename='myapp.log', level=logging.DEBUG)

# Obtain the `token_v2` value by inspecting your browser cookies on a logged-in (non-guest) session on Notion.so
client = NotionClient(
    token_v2=os.environ.get("NOTION_TOKEN"),
    monitor=True,
    start_monitoring=True)

# Replace this URL with the URL of the page you want to edit
projects_page = client.get_block("https://www.notion.so/" + os.environ.get("PROJECTS_PAGE"))

print("The title is:", projects_page.title)

def my_callback(record, difference):
    print("The record's title is now:", record.title)
    print("Here's what was changed:")
    print(difference)

# move my block to after the video
projects_page.add_callback(my_callback)

while True:
    sleep(1)
# Note: You can use Markdown! We convert on-the-fly to Notion's internal formatted text data structure.
# projects_page.title = "The title has now changed, and has *live-updated* in the browser!"