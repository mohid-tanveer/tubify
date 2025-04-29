import httpx
import re
import json
import asyncio
from urllib.parse import quote_plus
import html
from typing import List, Dict, Optional, Any


# helper function to decode html entities in video titles
def decode_video_title(title: str) -> str:
    """decode html entities in video titles"""
    if not title:
        return ""
    return html.unescape(title)


async def search_youtube_without_api(
    query: str, max_results: int = 5
) -> List[Dict[str, str]]:
    """
    Search YouTube without using the API by scraping search results page
    Returns a list of dictionaries with video id and title
    """
    # encode query for url
    encoded_query = quote_plus(query)

    # prepare request url - using the regular search page
    url = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAQ%253D%253D"  # filter for videos

    # set headers to mimic a browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            print(f"Sending YouTube web search request for: {query}")
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                print(f"YouTube search page error ({response.status_code})")
                return []

            # extract the initial data json from the page
            # YouTube stores search results in a variable called ytInitialData
            initial_data_match = re.search(
                r"var ytInitialData = (.+?);</script>", response.text
            )

            if not initial_data_match:
                print("Could not find search results data in the page")
                return []

            json_str = initial_data_match.group(1)
            data = json.loads(json_str)

            # extract videos from the search results
            videos = []

            # navigate the complex nested structure of YouTube's response
            try:
                # try to get contents from the two possible structures
                contents = (
                    data.get("contents", {})
                    .get("twoColumnSearchResultsRenderer", {})
                    .get("primaryContents", {})
                    .get("sectionListRenderer", {})
                    .get("contents", [])
                )

                if not contents:
                    print("No contents found in search results")
                    return []

                # find the item renderer section which contains video results
                video_renderers = []
                for content in contents:
                    if "itemSectionRenderer" in content:
                        for item in content["itemSectionRenderer"].get("contents", []):
                            if "videoRenderer" in item:
                                video_renderers.append(item["videoRenderer"])

                # process each video result
                for renderer in video_renderers[:max_results]:
                    if "videoId" in renderer and "title" in renderer:
                        video_id = renderer["videoId"]

                        # get title from runs if available
                        if "runs" in renderer["title"]:
                            title = " ".join(
                                [
                                    run.get("text", "")
                                    for run in renderer["title"]["runs"]
                                ]
                            )
                        else:
                            title = renderer["title"].get("simpleText", "")

                        # clean the title
                        title = decode_video_title(title)

                        videos.append({"id": video_id, "title": title})

                        if len(videos) >= max_results:
                            break

            except Exception as e:
                print(f"Error parsing YouTube search results: {str(e)}")
                return []

            print(f"YouTube web search for '{query}' returned {len(videos)} results")
            return videos

    except httpx.ReadTimeout:
        print(f"YouTube web search request timed out for query: {query}")
        return []
    except httpx.ConnectTimeout:
        print(f"YouTube web search connection timed out for query: {query}")
        return []
    except Exception as e:
        print(f"YouTube web search error for query '{query}': {str(e)}")
        return []


# function that gets video details using a single API call instead of a search
async def get_video_details(video_id: str, api_key: str) -> Dict[str, Any]:
    """
    Get video details using the videos.list endpoint which costs only 1 unit
    This is much more quota-efficient than search (1 unit vs 100 units)
    """
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={api_key}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)

            if response.status_code != 200:
                print(f"YouTube API error ({response.status_code}): {response.text}")
                return {}

            data = response.json()

            if "items" not in data or len(data["items"]) == 0:
                return {}

            item = data["items"][0]
            snippet = item.get("snippet", {})

            return {
                "id": video_id,
                "title": snippet.get("title", ""),
                "publishedAt": snippet.get("publishedAt", ""),
                "channelId": snippet.get("channelId", ""),
                "channelTitle": snippet.get("channelTitle", ""),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "categoryId": snippet.get("categoryId", ""),
            }
    except Exception as e:
        print(f"Error getting video details: {str(e)}")
        return {}


# Example hybrid approach
async def get_song_videos(
    song_name: str,
    artist_str: str,
    max_official: int = 1,
    max_live: int = 3,
    api_key: Optional[str] = None,
):
    """
    A hybrid approach that uses web scraping for search and API for details (if provided)
    1. Search YouTube via web scraping (no quota used)
    2. Optionally get details with API (1 quota unit per video) if api_key is provided
    """
    # search for official video
    official_query = f"{artist_str} {song_name} official video"
    official_videos = await search_youtube_without_api(official_query, max_official)

    # search for live performances
    live_query = f"{artist_str} {song_name} live performance"
    live_videos = await search_youtube_without_api(live_query, max_live)

    # if API key is provided, get additional details with the videos.list endpoint
    if api_key:
        enhanced_official_videos = []
        for video in official_videos:
            details = await get_video_details(video["id"], api_key)
            if details:
                enhanced_official_videos.append(details)
            else:
                enhanced_official_videos.append(video)

        enhanced_live_videos = []
        for video in live_videos:
            details = await get_video_details(video["id"], api_key)
            if details:
                enhanced_live_videos.append(details)
            else:
                enhanced_live_videos.append(video)

        return enhanced_official_videos, enhanced_live_videos

    return official_videos, live_videos
