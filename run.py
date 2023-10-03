import os
import requests
from dotenv import load_dotenv
import yaml
import PIL
from PIL import Image, ImageDraw
import base64
import json
import logging
import re

log_file = "jellybean.log"

if os.path.isfile(log_file):
    os.remove(log_file)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Ensure the needed folders exist
if not os.path.exists('./assets/originals/primary'):
    os.makedirs('./assets/originals/primary')
if not os.path.exists('./assets/originals/backdrop'):
    os.makedirs('./assets/originals/backdrop')
if not os.path.exists('./assets/originals/thumb'):
    os.makedirs('./assets/originals/thumb')
if not os.path.exists('./temp'):
    os.makedirs('./temp')
if not os.path.exists('./logs'):
    os.makedirs('./logs')

# Prepare logging
for file in os.listdir('./logs'):
    if file.endswith('.log'):
        os.remove(f'./logs/{file}')
log_file = "jellybean.log"

load_dotenv(".env")
emby_url = os.getenv('EMBY_URL')
api_key = os.getenv('EMBY_API_KEY')

with open('audio_codecs.yml', 'r') as file:
    regexes = yaml.safe_load(file)
    audio_regex = regexes['regex']

def main():

    response = requests.get(f"{emby_url}/Users",
                            headers={"X-Emby-Token": api_key})

    users = response.json()

    for user in users:
        if user["Policy"]["IsAdministrator"]:
            global user_id
            user_id = user["Id"]
            logging.info(f"Admin user ID: {user_id}")
            break

    with open("config.yaml", "r") as file:
        config_vars = yaml.safe_load(file)

    libraries = config_vars["libraries"]
    logging.info(f"Loaded config.yaml:\n {libraries}")

    libraries_dict = {}

    for library in libraries:

        response = requests.get(f"{emby_url}/Users/{user_id}/Views",
                                headers={"X-Emby-Token": api_key})

        views = response.json()["Items"]

        for view in views:
            if view['Name'] == library:
                parent_id = view["Id"]
                logging.info(f"Parent ID: {parent_id}")
                collection_type = view["CollectionType"]
                logging.info(f'Collection Type: {collection_type}')
                break
            else:
                parent_id = None
                collection_type = None

        libraries_dict.update({library: {"parent_id": parent_id, "collection_type": collection_type}})

    for library in libraries_dict:

        logging.info(f"Checking {library}")

        library_type = libraries_dict[library].get('collection_type')

        items = get_all_items_library(libraries_dict[library])

        if library_type == 'none':
            logging.info(f"{library}: Library is not set to movies or tv shows, skipping library.")
            continue

        if not config_vars["libraries"][library]["enabled"]:
            logging.info(
                f"Library Name: {library} \nLibrary Type: {library_type}\nAction: Library is not enabled in the config.yaml file, skipping library.\n------")
            continue

        logging.info(
            f"Library Name: {library} \nLibrary Type: {library_type}\nAction: Library is enabled in the config.yaml file, checking overlays.\n------")
        overlays(library, library_type, items, config_vars)


def collection(library, library_type, items, filename):
    # Get the config from the filename
    with open(f"./collections/{filename}", "r") as file:
        config_vars = yaml.safe_load(file)

    # Create an empty dictionary to store the collections
    collections_dict = {}

    # Iterate over collections
    for collection_name, collection_data in config_vars["collections"].items():
        # Add the sub-section to the collections dictionary
        collections_dict[collection_name] = collection_data

    # Get a list of all existing collections in the Emby server
    response = requests.get(f"{emby_url}/Users/{user_id}/Views",
                            headers={"X-Emby-Token": api_key})

    collections = response.json()["Items"]

    # Loop through all collections
    for collection_name, collection_data in collections_dict.items():
        logging.info(f"Checking {collection_name}")
        collection_type = collection_data["type"]
        logging.info(f"Collection Type: {collection_type}")
        collection_link = collection_data["link"]
        logging.info(f"Collection Link: {collection_link}")
        collection_limit = collection_data["limit"]
        logging.info(f"Collection Limit: {collection_limit}")

        # Check if collection exists in the server


def overlays(library, library_type, items, config_vars):
    overlay_config = config_vars["libraries"][library]["overlays"]

    if overlay_config:
        logging.info(f"{library}: Overlays is true in the config.yaml file, adding missing overlays.")
    else:
        logging.info(f"{library}: Overlays is false in the config.yaml file, removing overlays.")

    # MOVIES
    if library_type == 'movies':
        logging.info(f"Found {len(items)} items in {library}")
        for item in items:
            logging.info(f"Checking {item['Name']}: {item['Id']}")
            response2 = requests.get(f"{emby_url}/Users/{user_id}/Items/{item['Id']}",
                                     headers={"X-Emby-Token": api_key})

            movie = response2.json()

            if not 'MediaSources' in movie:
                logging.info(f"Movie {item['Name']} has no media sources, skipping.")
                continue

            tagged = check_tags(movie)

            tag = {'Name': 'custom-overlay'}

            if overlay_config:
                if tagged:
                    logging.info(f"{item['Name']} has custom overlay, skipping.")
                    continue
                logging.info(
                    f"{item['Name']} does not have a custom overlay. Adding overlay to {item['Name']}: {item['Id']}")
                if add_overlay(movie["Id"], item, 'primary'):
                    add_overlay(movie["Id"], item, 'thumb')
                    update_tag(movie, item, True, tag)
            else:
                if not tagged:
                    logging.info(f"{item['Name']} does not have a custom overlay, skipping.")
                    continue
                logging.info(f"{item['Name']} has a custom overlay. Removing overlay from {item['Name']}: {item['Id']}")
                if remove_overlay(movie["Id"], item, 'primary'):
                    remove_overlay(movie["Id"], item, 'thumb')
                    update_tag(movie, item, False, tag)

    # TV SHOWS
    elif library_type == 'tvshows':
        logging.info(f'Found {len(items)} items in {library}')
        # Loop through all tv shows
        for item in items:

            response2 = requests.get(f"{emby_url}/Users/{user_id}/Items/{item['Id']}",
                                     headers={"X-Emby-Token": api_key})
            tv_show = response2.json()

            logging.info(f"Checking {item['Name']}: {tv_show['Id']}")

            response3 = requests.get(f"{emby_url}/Shows/{tv_show['Id']}/Episodes",
                                     headers={"X-Emby-Token": api_key})
            try:
                episodes = response3.json()['Items']
            except json.JSONDecodeError:
                logging.info(f"TV Show {item['Name']} has no episodes, skipping.")
                continue

            if len(episodes) == 0:
                logging.info(f"TV Show {item['Name']} has no episodes, skipping.")
                continue
            episode_id = episodes[0]["Id"]

            if episode_id is None:
                logging.info(f"TV Show {item['Name']} has no episodes, skipping.")
                continue

            response4 = requests.get(f"{emby_url}/Users/{user_id}/Items/{episode_id}",
                                     headers={"X-Emby-Token": api_key})

            episode = response4.json()

            if not 'MediaSources' in episode:
                logging.info(f"Episode {episode['Name']} has no media sources, skipping.")
                continue

            tagged = check_tags(tv_show)
            tag = {'Name': 'custom-overlay'}
            if overlay_config:
                if tagged:
                    continue
                logging.info(f"Adding overlay to {item['Name']}: {tv_show['Id']}")
                if add_overlay(tv_show["Id"], item, 'primary'):
                    add_overlay(tv_show["Id"], item, 'thumb')
                    update_tag(tv_show, item, True, tag)
            else:
                if not tagged:
                    continue
                logging.info(f"Removing overlay from {item['Name']}: {tv_show['Id']}")
                if remove_overlay(tv_show["Id"], item, 'primary'):
                    remove_overlay(tv_show["Id"], item, 'thumb')
                    update_tag(tv_show, item, False, tag)


def get_all_items_library(library):
    if library['collection_type'] == 'movies':
        response = requests.get(f"{emby_url}/Items",
                                headers={"X-Emby-Token": api_key},
                                params={"ParentId": library["parent_id"],
                                        "Recursive": "true"})
        items_recursive = response.json()["Items"]
        items = [item for item in items_recursive if not item.get('IsFolder')]
    else:
        response = requests.get(f"{emby_url}/Items",
                                headers={"X-Emby-Token": api_key},
                                params={"ParentId": library["parent_id"]})
        items = response.json()["Items"]
    return items


def check_tags(file):
    exists = any(item['Name'] == "custom-overlay" for item in file['TagItems'])
    return exists

def check_hdr(item):
    # Get movie from item
    response = requests.get(f"{emby_url}/Users/{user_id}/Items/{item['Id']}",
                            headers={"X-Emby-Token": api_key})

    media_file = response.json()

    # Check if media_file has "Type": "Series"
    if media_file["Type"] == "Series":
        logging.info("Media file is a TV show, getting the first episode")
        # Get all episodes from that TV Show
        response2 = requests.get(f"{emby_url}/Shows/{media_file['Id']}/Episodes",
                                 headers={"X-Emby-Token": api_key})

        episodes = response2.json()['Items']

        episode_id = episodes[0]["Id"]

        response3 = requests.get(f"{emby_url}/Users/{user_id}/Items/{episode_id}",
                                 headers={"X-Emby-Token": api_key})
        episode = response3.json()

        media_file = episode
    path = media_file['MediaSources'][0]['Path']
    if media_file['Width'] >= 2500:
        logging.info(f"Media file: {media_file['Name']}, and path is: {path}")
        if 'DV' in path:
            if 'HDR' in path:
                logging.info("Media file is DV + HDR")
                return '4KDVHDR'
            logging.info("Media file is DV")
            return '4KDV'
        elif 'HDR' in path:
            if 'HDR10Plus' in path:
                logging.info("Media file is HDR10+")
                return '4KHDRPLUS'
            logging.info("Media file is HDR")
            return '4KHDR'
        else:
            logging.info("Media file is SDR")
            return '4KSDR'
    else:
        # Placeholder
        return '1080p'

def check_audio(item):
    response = requests.get(f"{emby_url}/Users/{user_id}/Items/{item['Id']}",
                            headers={"X-Emby-Token": api_key})

    media_file = response.json()

    # Check if media_file has "Type": "Series"
    if media_file["Type"] == "Series":
        logging.info("Media file is a TV show, getting the first episode")
        # Get all episodes from that TV Show
        response2 = requests.get(f"{emby_url}/Shows/{media_file['Id']}/Episodes",
                                 headers={"X-Emby-Token": api_key})

        episodes = response2.json()['Items']

        # Get the first episode ID
        episode_id = episodes[0]["Id"]

        response3 = requests.get(f"{emby_url}/Users/{user_id}/Items/{episode_id}",
                                 headers={"X-Emby-Token": api_key})

        episode = response3.json()

        media_file = episode

    # Check if media_file resolution is 4K
    path = media_file['MediaSources'][0]['Path']

    for condition in audio_regex:
        key = condition["key"]
        regex = condition["value"]

        if re.search(regex, path):
            logging.info(f"Media file has audio codec: {key}")
            return key
    return None


def update_tag(movie, item, add, tag):
    if add:
        movie["TagItems"].append(tag)
    else:
        for tags in movie['TagItems']:
            if tags['Name'] == "custom-overlay":
                movie['TagItems'].remove(tags)
                break

    response3 = requests.post(f"{emby_url}/Items/{item['Id']}",
                              headers={"X-Emby-Token": api_key,
                                       "Content-Type": "application/json"},
                              data=json.dumps(movie))

    if response3.status_code == 204:
        logging.info(f'Tag for {item["Name"]} updated successfully')
    else:
        logging.info(f'Failed to update tag for {item["Name"]}')


def add_overlay(movie_id, item, image_type):
    logging.info(f"Adding {image_type} overlay to {item['Name']}: {movie_id}")

    response = requests.get(f"{emby_url}/Items/{movie_id}/Images",
                            headers={"X-Emby-Token": api_key})

    image_data = response.json()

    if len(image_data) == 0:
        logging.info(f"Movie {item['Name']} has no poster, skipping.")
        return False

    # Save a copy of the original image
    response = requests.get(f"{emby_url}/Items/{movie_id}/Images/{image_type}",
                            headers={"X-Emby-Token": api_key})

    if image_type == 'thumb' and response.status_code == 404:
        logging.info(f"Movie {item['Name']} has no thumb, looking for backdrop.")
        image_type = 'backdrop'
        response = requests.get(f"{emby_url}/Items/{movie_id}/Images/{image_type}",
                                headers={"X-Emby-Token": api_key})

    with open(f"./assets/originals/{image_type}/{movie_id}.jpg", "wb") as f:
        f.write(response.content)

    resolution_overlay_name = check_hdr(item)
    audio_overlay_name = check_audio(item)

    # Check if the images exists
    if not os.path.exists(f'./assets/originals/{image_type}/{movie_id}.jpg'):
        logging.info(f"{item['Name']} does not have a {image_type} image, skipping.")
        return False

    # Check if the overlay file exists
    if not os.path.exists(f'./assets/overlays/resolution/{resolution_overlay_name}.png'):
        logging.error(f"Overlay {resolution_overlay_name}.png does not exist, skipping.")
        return False
    if not os.path.exists(f'./assets/overlays/audio/{audio_overlay_name}.png'):
        logging.error(f"Overlay {audio_overlay_name}.png does not exist, skipping.")
        return False

    try:
        original_image = Image.open(f'./assets/originals/{image_type}/{movie_id}.jpg')
    except PIL.UnidentifiedImageError:
        logging.error(f"Unable to open {image_type}/{movie_id}.jpg, skipping.")
        os.remove(f'./assets/originals/{image_type}/{movie_id}.jpg')
        return False
    except FileNotFoundError:
        logging.error(f"Poster not found for {movie_id}.jpg, skipping.")
        return False

    resolution_overlay_image = Image.open(f'./assets/overlays/resolution/{resolution_overlay_name}.png')
    audio_overlay_image = Image.open(f'./assets/overlays/audio/{audio_overlay_name}.png')

    width, height = resolution_overlay_image.size
    if image_type == 'primary':
        composite_image = original_image.convert("RGBA").resize((1000, 1500))
    elif image_type == 'thumb':
        composite_image = original_image.convert("RGBA").resize((1000, 562))
        resolution_overlay_image = resolution_overlay_image.resize((int(width / 1.5), int(height / 1.5)))
    elif image_type == 'backdrop':
        composite_image = original_image.convert("RGBA").resize((3840, 2160))
        resolution_overlay_image = resolution_overlay_image.resize((int(width * 2.5637), int(height * 2.5637)))

    # Calculate the position for the overlay image
    overlay_x = 30
    if image_type == 'primary':
        overlay_y = 50
    elif image_type == 'thumb':
        overlay_y = 30
    elif image_type == 'backdrop':
        overlay_x = 115
        overlay_y = 134

    overlay_resolution_x = overlay_x + 20
    overlay_resolution_y = overlay_y + 20

    # Calculate the position for the semi-transparent background
    background_height = overlay_resolution_y + resolution_overlay_image.height + 20

    # Calculate the position for the resolution overlay with offsets
    overlay_resolution_x = overlay_x + 20
    overlay_resolution_y = overlay_y + 20

    # Calculate the position for the audio codec overlay with offsets
    overlay_audio_x = (composite_image.width - audio_overlay_image.width) // 2
    overlay_audio_y = background_height - audio_overlay_image.height - 20

    # Create a semi-transparent background with rounded corners larger than the overlay image
    overlay_width, overlay_height = resolution_overlay_image.size
    if image_type == 'primary':
        overlay_with_background_size = (overlay_width + 50, overlay_height + 50)
        corner_radius = 25
    elif image_type == 'thumb':
        overlay_with_background_size = (overlay_width + 20, overlay_height + 20)
        corner_radius = 15
    elif image_type == 'backdrop':
        overlay_with_background_size = (overlay_width + 76, overlay_height + 76)
        corner_radius = 50

    overlay_with_background = Image.new("RGBA", overlay_with_background_size)
    background_color = (0, 0, 0, 160)
    overlay_mask = Image.new("L", overlay_with_background_size, 0)
    overlaymask_draw = ImageDraw.Draw(overlay_mask)
    mask_draw = ImageDraw.Draw(overlay_mask)
    mask_draw.rounded_rectangle([(0, 0), overlay_with_background_size], corner_radius, fill=255)
    overlay_with_background.paste(background_color, mask=overlay_mask)

    if image_type == 'primary':
        composite_image.alpha_composite(overlay_with_background, (overlay_resolution_x - 25, overlay_resolution_y - 20))
        composite_image.alpha_composite(resolution_overlay_image, (overlay_resolution_x, overlay_resolution_y))
    elif image_type == 'thumb':
        composite_image.alpha_composite(overlay_with_background, (overlay_resolution_x - 25, overlay_resolution_y - 20))
        composite_image.alpha_composite(resolution_overlay_image,(overlay_resolution_x - 15, overlay_resolution_y - 10))
    elif image_type == 'backdrop':
        composite_image.alpha_composite(overlay_with_background, (overlay_resolution_x - 40, overlay_resolution_y - 33))
        composite_image.alpha_composite(resolution_overlay_image, (overlay_resolution_x, overlay_resolution_y))

    # Create a semi-transparent background for the audio codec overlay
    audio_overlay_with_background_size = (audio_overlay_image.width + 50, audio_overlay_image.height + 50)
    audio_overlay_with_background = Image.new("RGBA", audio_overlay_with_background_size)
    audio_overlay_mask = Image.new("L", audio_overlay_with_background_size, 0)
    audio_overlay_mask_draw = ImageDraw.Draw(audio_overlay_mask)
    audio_overlay_mask_draw.rounded_rectangle([(0, 0), audio_overlay_with_background_size], corner_radius, fill=255)
    audio_overlay_with_background.paste(background_color, mask=audio_overlay_mask)

    # Paste the semi-transparent background for the audio overlay onto the composite image
    if image_type == 'primary':
        composite_image.alpha_composite(audio_overlay_with_background, (overlay_audio_x - 25, overlay_audio_y - 20))
        composite_image.alpha_composite(audio_overlay_image, (overlay_audio_x, overlay_audio_y))

    composite_image.convert('RGB').save(f'./temp/{movie_id}.jpg', 'JPEG')

    response = requests.delete(f"{emby_url}/Items/{movie_id}/Images/{image_type}",
                                   headers={"X-Emby-Token": api_key})

    # Upload the new image to the server
    with open(f'./temp/{movie_id}.jpg', 'rb') as file:
        image_data = file.read()

    image_data_base64 = base64.b64encode(image_data)

    headers = {"X-Emby-Token": api_key,
               "Content-Type": "image/jpeg"}
    url = f"{emby_url}/Items/{movie_id}/Images/{image_type}/"

    response = requests.post(url, headers=headers, data=image_data_base64)

    if response.status_code == 204:
        logging.info('Image uploaded successfully')
        os.remove(f'./temp/{movie_id}.jpg')
        return True
    else:
        logging.info('Failed to upload image')
        logging.info(f'Response: {response.text}')
        return False


def remove_overlay(movie_id, item, image_type):
    response = requests.get(f"{emby_url}/Items/{movie_id}/Images",
                            headers={"X-Emby-Token": api_key})

    image_data = response.json()

    if len(image_data) == 0:
        # print(f"Movie {item['Name']} has no poster, skipping.")
        return False

    try:
        # Upload the new image to the server
        with open(f'./assets/originals/{image_type}/{movie_id}.jpg', 'rb') as file:
            image_data = file.read()
    except FileNotFoundError:
        logging.error(f"Unable to open {image_type}/{movie_id}.jpg, skipping.")
        return False

    image_data_base64 = base64.b64encode(image_data)

    # Define the headers for the request
    headers = {"X-Emby-Token": api_key,
               "Content-Type": "image/jpeg"}

    # Define the endpoint URL
    url = f"{emby_url}/Items/{movie_id}/Images/{image_type}"

    # Send the POST request
    response = requests.post(url, headers=headers, data=image_data_base64)

    # print(response)

    # Check the response
    if response.status_code == 204:
        logging.info(f'{image_type} image uploaded successfully')
        os.remove(f'./assets/originals/{image_type}/{movie_id}.jpg')
        return True
    else:
        logging.info('Failed to upload image')
        logging.info(f'Response: {response.text}')
        return False


if __name__ == '__main__':
    main()
