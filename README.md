# Jellybean
An overlay tool for [Emby](https://emby.media/)

## What it does so far
Scans the file and applies the following overlays: 

- 4K UHD
- 4K HDR
- 4K Dolby Vision
- 4K Dolby Vision with HDR fallback

Run it only on 4K libraries!

The script saves a backup of the original poster to `assets/originals`. Running the script with `overlays: false` will restore the backup.

Tested on Linux, Emby Beta Version: 4.8.0.46
## Getting started

Edit the `.env` and the `config.yaml`

``` 
python3 run.py
```

## About
This project is a work in progress. I wanted a way to replicate what PMM does with 4K Overlays in Emby.

It is not affiliated with Emby. It is not endorsed by Emby.

Heavily inspired by [Plex-Meta-Manager](https://github.com/meisnate12/Plex-Meta-Manager)

Overlay images by [Plex-Meta-Manager](https://github.com/meisnate12/Plex-Meta-Manager)
