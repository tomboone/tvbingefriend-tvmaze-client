# BingeFriend TVMaze Client

Python client using the [TV Maze API](https://www.tvmaze.com/api) to fetch show, season, and episode data.

## Usage

Here's a quick example of how to import and use the `TVMazeAPI` client to fetch details for a show.

```python
from tvbingefriend_tvmaze_client.tvmaze_api import TVMazeAPI

# Initialize the client
client = TVMazeAPI()

# Fetch details for a specific show (e.g., "Under the Dome", ID: 1)
show_details = client.get_show_details(1)
if show_details:
    print(f"Show Name: {show_details.get('name')}")

# Fetch seasons for the show
seasons = client.get_seasons(1)
if seasons:
    print(f"Seasons: {len(seasons)}")

# Fetch episodes for the show
episodes = client.get_episodes(1)
if episodes:
    print(f"Episodes: {len(episodes)}")

# Fetch show updates for a period of time
updates = client.get_show_updates(period='day')
if updates:
    print(f"Show Updates: {len(updates)}")
```

## Attribution

Data provided by [TVmaze.com](https://www.tvmaze.com/).

This client uses the TV Maze API but is not endorsed or certified by TV Maze.