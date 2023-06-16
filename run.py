from distutils import config
import os
import requests
from dotenv import load_dotenv
import yaml
from PIL import Image
import base64
import json
import logging
import datetime

# Ensure the needed folders exist
if not os.path.exists('./assets/originals'):
    os.makedirs('./assets/originals')

if not os.path.exists('./temp'):
    os.makedirs('./temp')

if not os.path.exists('./logs'):
    os.makedirs('./logs')

# Remove any existing log files
for file in os.listdir('./logs'):
    if file.endswith('.log'):
        os.remove(f'./logs/{file}')

# Generate a unique log file name using a timestamp
log_file = f"./logs/jellybean.log"

# Configure the logging settings
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load .env file
load_dotenv(".env")

# Global variables
jellyfin_url = os.getenv('JELLYFIN_URL')
api_key = os.getenv('JELLYFIN_API_KEY')


def main():
    
    # Get admin user ID
    response = requests.get(f"{jellyfin_url}/Users",
                            headers={"X-Emby-Token": api_key})

    users = response.json()

    for user in users:
        if user["Policy"]["IsAdministrator"]:
            global user_id
            user_id = user["Id"]
            break

    # Get list of libraries from the config.yaml file
    with open("config.yaml", "r") as file:
        config_vars = yaml.safe_load(file)

    libraries = config_vars["libraries"]

    # Initialize empty list of library parent ids
    libraries_dict = {}



    # Get the parent id of each library
    for library in libraries:

        # Get all items
        response = requests.get(f"{jellyfin_url}/Users/{user_id}/Views",
                                headers={"X-Emby-Token": api_key})
        
        print(library)

        views = response.json()["Items"]

        for view in views:
            print(f"View Name: {view['Name']}")
            if view['Name'] == library:
                parent_id = view["Id"]
                print(f"Parent ID: {parent_id}")
                collection_type = view["CollectionType"]
                print(f'Collection Type: {collection_type}')
                break

        # Add the library name and parent id to the dictionary

        libraries_dict.update({library: {"parent_id": parent_id, "collection_type": collection_type}})

    #print(libraries_dict)

    # Cycle through the libraries
    for library in libraries_dict:

        print(f"Checking {library}")
        logging.info(f"Checking {library}")

        library_type = libraries_dict[library].get('collection_type')

        # Call function to get list of items in the library
        items = get_all_items_library(libraries_dict[library])

        # Check CollectionType
        

        if library_type == 'none':
            print(f"{library}: Library is not set to movies or tv shows, skipping library.")
            logging.info(f"{library}: Library is not set to movies or tv shows, skipping library.")
            continue

        # Check if library is set to skip
        if config_vars["libraries"][library]["skip"]:
            print(f"Library Name: {library} \nLibrary Type: {library_type}\nAction: Skip is set to true in the config.yaml file, skipping library.\n------")
            continue
        
        # Check if overlays will be added or removed
        overlay_config = config_vars["libraries"][library]["overlays"]

        # Check if Overlays is set to true
        if overlay_config:
            print(f"{library}: Overlays is true in the config.yaml file, adding missing overlays.")
            logging.info(f"{library}: Overlays is true in the config.yaml file, adding missing overlays.")
        else:
            print(f"{library}: Overlays is false in the config.yaml file, removing overlays.")
            logging.info(f"{library}: Overlays is false in the config.yaml file, removing overlays.")

        

        #### MOVIES ####

        if library_type == 'movies':
            # Loop through all movies
            print(f"Found {len(items)} items in {library}")
            logging.info(f"Found {len(items)} items in {library}")
            for item in items:

                response2 = requests.get(f"{jellyfin_url}/Users/{user_id}/Items/{item['Id']}",
                                    headers={"X-Emby-Token": api_key})
                
                movie = response2.json()

                if not 'MediaSources' in movie:
                    print(f"Movie {item['Name']} has no media sources, skipping.")
                    logging.info(f"Movie {item['Name']} has no media sources, skipping.")
                    continue

                tagged = check_tags(movie)

                if overlay_config:
                    if tagged:
                        continue
                    if add_overlay(movie["Id"], item):
                        update_tag(movie, item, True)
                else:
                    if not tagged:
                        continue
                    if remove_overlay(movie["Id"], item):
                        update_tag(movie, item, False)

        ### TV SHOWS ###

        elif library_type == 'tvshows':
            print(f'Found {len(items)} items in {library}')
            logging.info(f'Found {len(items)} items in {library}')
            # Loop through all tv shows
            for item in items:

                response2 = requests.get(f"{jellyfin_url}/Users/{user_id}/Items/{item['Id']}",
                                    headers={"X-Emby-Token": api_key})
                
                tv_show = response2.json()

                # Get all episodes from that TV Show
                response3 = requests.get(f"{jellyfin_url}/Shows/{tv_show['Id']}/Episodes",
                                    headers={"X-Emby-Token": api_key})
            
                episodes = response3.json()['Items']

                # Get the first episode ID
                episode_id = episodes[0]["Id"]

                # Check that episode_id is not None
                if episode_id is None:
                    print(f"TV Show {item['Name']} has no episodes, skipping.")
                    logging.info(f"TV Show {item['Name']} has no episodes, skipping.")
                    continue

                response4 = requests.get(f"{jellyfin_url}/Users/{user_id}/Items/{episode_id}",
                                    headers={"X-Emby-Token": api_key})
                
                episode = response4.json()

                # Get MediaSources from first episode
                if not 'MediaSources' in episode:
                    print(f"Episode {episode['Name']} has no media sources, skipping.")
                    logging.info(f"Episode {episode['Name']} has no media sources, skipping.")
                    continue

                #print(f'MediaSources: {episode["MediaSources"]}')

                tagged = check_tags(tv_show)

                if overlay_config:
                    if tagged:
                        continue
                    logging.info(f"Adding overlay to {item['Name']}: {tv_show['Id']}")
                    print(f"Adding overlay to {item['Name']}: {tv_show['Id']}")
                    if add_overlay(tv_show["Id"], item):
                        update_tag(tv_show, item, True)
                else:
                    if not tagged:
                        continue
                    logging.info(f"Removing overlay from {item['Name']}: {tv_show['Id']}")
                    print(f"Removing overlay from {item['Name']}: {tv_show['Id']}")
                    if remove_overlay(tv_show["Id"], item):
                        update_tag(tv_show, item, False)

def get_all_items_library(library):
    # Get all items in the library
    response = requests.get(f"{jellyfin_url}/Items",
                            headers={"X-Emby-Token": api_key},
                            params={"ParentId": library["parent_id"]})    

    items = response.json()["Items"]
    return items                  

def check_tags(movie):

    # Check if the movie has the tag "custom-overlay"
    if "custom-overlay" in movie["Tags"]:
        print(f"{movie['Name']} has custom overlay.")
        return True
    else:
        print(f"{movie['Name']} does not have custom overlay.")
        return False

def check_color(item):

    # Get movie from item
    response = requests.get(f"{jellyfin_url}/Users/{user_id}/Items/{item['Id']}",
                        headers={"X-Emby-Token": api_key})
    
    media_file = response.json()

    # Check if media_file has "Type": "Series"
    if media_file["Type"] == "Series":
        print("Media file is a TV show")
        # Get all episodes from that TV Show
        response2 = requests.get(f"{jellyfin_url}/Shows/{media_file['Id']}/Episodes",
                            headers={"X-Emby-Token": api_key})
    
        episodes = response2.json()['Items']

        # Get the first episode ID
        episode_id = episodes[0]["Id"]

        response3 = requests.get(f"{jellyfin_url}/Users/{user_id}/Items/{episode_id}",
                            headers={"X-Emby-Token": api_key})
        
        episode = response3.json()

        media_file = episode

    # Check if the movie is SDR, HDR, or DoVI
    for media_source in media_file['MediaSources']:
        for media_stream in media_source['MediaStreams']:
            if media_stream['Codec'] == 'hevc' or media_stream['Codec'] == 'h264' or media_stream['Codec'] == 'vp9' or media_stream['Codec'] == 'av1':
                if media_stream['VideoRange'] == 'SDR' and media_stream['VideoRangeType'] == 'SDR':
                    print("Color space is SDR")
                    return '4KSDR'
                elif media_stream['VideoRange'] == 'HDR' and (media_stream['VideoRangeType'].startswith('HDR10') or media_stream['VideoRangeType'].startswith('HLG')):
                    if 'VideoDoViTitle' in media_stream:
                        if media_stream['VideoDoViTitle'].startswith('DV Profile'):
                            print("Color space is DV + HDR")
                            return '4KDVHDR'
                    else:
                        print("Color space is HDR Only")
                        return '4KHDR'
                elif media_stream['VideoRange'] == 'HDR' and media_stream['VideoRangeType'] == 'DOVI':
                    if 'VideoDoViTitle' in media_stream and media_stream['VideoDoViTitle'].startswith('DV Profile'):
                        print("Color space is DV only")
                        return '4KDV'
                    else:
                        print("Unknown color space")
                        return '4KSDR'
                else:
                    print("Unknown color space") 
                    return '4KSDR'

def update_tag(movie, item, add):
    
        if add:
            # Add the tag "custom-overlay" to the movie
            movie["Tags"].append("custom-overlay")
        else:
            # remove the tag "custom-overlay" to the movie
            movie["Tags"].remove("custom-overlay")

        # Update the movie in the Jellyfin server
        response3 = requests.post(f"{jellyfin_url}/Items/{item['Id']}",
                        headers={"X-Emby-Token": api_key,
                                "Content-Type": "application/json"},
                        data=json.dumps(movie))
    
        # Print response from the request
    
        if response3.status_code == 204:
            print(f'Movie {item["Name"]} updated successfully')
        else:
            print(f'Failed to update movie {item["Name"]}')

def add_overlay(movie_id, item):

    print(f"Adding overlay to {item['Name']}: {movie_id}")
    logging.info(f"Adding overlay to {item['Name']}: {movie_id}")
    
    response = requests.get(f"{jellyfin_url}/Items/{movie_id}/Images",
                         headers={"X-Emby-Token": api_key})

    image_data = response.json()

    if len(image_data) == 0:
        print(f"Movie {item['Name']} has no poster, skipping.")
        logging.info(f"Movie {item['Name']} has no poster, skipping.")    
        return False

    # Save a copy of the original poster
    response = requests.get(f"{jellyfin_url}/Items/{movie_id}/Images/Primary",
                            headers={"X-Emby-Token": api_key})
    
    with open(f"./assets/originals/{movie_id}.jpg", "wb") as f:
        f.write(response.content)

    overlay_name = check_color(item)

    # combine poster with the 4kdv logo
    img1 = Image.open(f'./assets/originals/{movie_id}.jpg')
    img2 = Image.open(f'./assets/overlays/{overlay_name}.png')

    # Resize the second image to match the first one if they have different sizes
    if img1.size != img2.size:
        img2 = img2.resize(img1.size)

    # Overlay the transparent image on top of the first image
    combined = Image.alpha_composite(img1.convert('RGBA'), img2.convert('RGBA'))

    # Save the new image
    combined.convert('RGB').save(f'./temp/{movie_id}.jpg', 'JPEG')
    #print("Image merged successfully")
    
    # Upload the new image to the server
    with open(f'./temp/{movie_id}.jpg', 'rb') as file:
        image_data = file.read()

    image_data_base64 = base64.b64encode(image_data)

    # Define the headers for the request
    headers = {"X-Emby-Token": api_key,
            "Content-Type": "image/jpeg"}

    # Define the endpoint URL
    url = f"{jellyfin_url}/Items/{movie_id}/Images/Primary"

    # Send the POST request
    response = requests.post(url, headers=headers, data=image_data_base64)

    #print(response)

    # Check the response
    if response.status_code == 204:
        print('Image uploaded successfully')
        logging.info('Image uploaded successfully') 
        os.remove(f'./temp/{movie_id}.jpg')
        return True
    else:
        print('Failed to upload image')
        logging.info('Failed to upload image')
        print('Response:', response.text)
        logging.info(f'Response: {response.text}') 
        return False

def remove_overlay(movie_id, item):

    response = requests.get(f"{jellyfin_url}/Items/{movie_id}/Images",
                        headers={"X-Emby-Token": api_key})

    image_data = response.json()

    if len(image_data) == 0:
        print(f"Movie {item['Name']} has no poster, skipping.")
        return False
    
    # Upload the new image to the server
    with open(f'./assets/originals/{movie_id}.jpg', 'rb') as file:
        image_data = file.read()

    image_data_base64 = base64.b64encode(image_data)

    # Define the headers for the request
    headers = {"X-Emby-Token": api_key,
            "Content-Type": "image/jpeg"}

    # Define the endpoint URL
    url = f"{jellyfin_url}/Items/{movie_id}/Images/Primary"

    # Send the POST request
    response = requests.post(url, headers=headers, data=image_data_base64)

    #print(response)

    # Check the response
    if response.status_code == 204:
        print('Image uploaded successfully')
        os.remove(f'./assets/originals/{movie_id}.jpg')
        return True
    else:
        print('Failed to upload image')
        print('Response:', response.text)
        return False

if __name__ == '__main__':

    main()
