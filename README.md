# Jellybean
An overlay and (*soon*) collection manager for [Jellyfin](https://github.com/jellyfin/jellyfin)

<img width="575" alt="CleanShot 2023-06-15 at 21 48 27@2x" src="https://github.com/EduAndino17/jellybean/assets/11341292/4c8c66dd-519a-4ddc-bb86-5347e27acf0e">

## What it does so far
Scans the file and applies the following overlays: 

- 4K UHD
- 4K HDR
- 4K Dolby Vision
- 4K Dolby Vision with HDR fallback

Run it only on 4K libraries!

The script saves a backup of the original poster to `assets/originals`. Running the script with `overlays: false` will restore the backup.

Tested on Linux, Jellyfin Version: 10.8.10 
## Getting started

Edit the `.env` and the `config.yaml`

``` 
python3 run.py
```

## Next steps

- Emby Support
- Collections

## About
This project is a work in progress. I wanted a way to replicate what PMM does with 4K Overlays in Jellyfin.

It is not affiliated with Jellyfin. It is not endorsed by Jellyfin.

Heavily inspired by [Plex-Meta-Manager](https://github.com/meisnate12/Plex-Meta-Manager)

Overlay images by [Plex-Meta-Manager](https://github.com/meisnate12/Plex-Meta-Manager)
