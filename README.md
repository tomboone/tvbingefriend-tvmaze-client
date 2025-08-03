# BingeFriend TVMaze Client

Python client using the [TV Maze API](https://www.tvmaze.com/api) to fetch show, season, episode, network, and webchannel data.

## Usage

Here's a quick example of how to import and use the `TVMazeAPI` client to fetch details for a show.

```python
from tvbingefriend_tvmaze_client.tvmaze_api import TVMazeAPI

# Initialize the client
client = TVMazeAPI()

# Fetch a page of shows (page integer starts from 0, e.g., page=0)
shows = client.get_shows(page=0)
if shows:
    print(f"Shows on page 0: {len(shows)}")

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

# Fetch network details for a specific network ID
network = client.get_network(1)
if network:
    print(f"Network Name: {network.get('name')}")

# Fetch webchannel details for a specific webchannel ID
webchannel = client.get_webchannel(1)
if webchannel:
    print(f"Webchannel Name: {webchannel.get('name')}")

# Fetch show updates for a period of time
updates = client.get_show_updates(period='day')
if updates:
    print(f"Show Updates: {len(updates)}")
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Attribution

Data provided by [TVmaze.com](https://www.tvmaze.com/).

This client uses the TV Maze API but is not endorsed or certified by TV Maze.