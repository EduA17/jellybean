# Jellybean
An overlay tool for [Emby](https://emby.media/)

## What it does so far
Scans the file and applies the following overlays to the main poster: 

- 4K UHD
- 4K HDR
- 4K Dolby Vision
- 4K Dolby Vision with HDR fallback
- Audio codecs

![](<CleanShot 2023-10-04 at 16.47.38@2x-1.png>)

It also adds overlays to the thumb or backdrop image for continue watching

![](<CleanShot 2023-10-04 at 16.50.03@2x.png>)

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

Overlay images by [Plex-Meta-Manager](https://github.com/meisnate12/Plex-Meta-Manager)
