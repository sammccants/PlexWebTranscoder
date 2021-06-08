# PlexWeb Transcoder

This script allows you to easily transcode batches of videos using ffmpeg. The original intention is to allow you to pre-transcode videos (before adding them to your Plex server) to the format and video/audio encodings that can be viewed in the PlexWeb app. This allows you to stream from a computationally weak server (like a Raspberry Pi) without having to worry about files failing to play because the server needs to transcode the video or audio and isn't powerful enough.

Though this is the reason for the creation of the script, and it dictates the default settings, you could also use the script to do simple batch transcoding of any video files, however you like.

Basically all it does is to walk through the files in the input folder, find any video files that don't match one of the video or audio encodings you want to allow, and transcodes them to the desired encodings. You can set options to change parts of its behavior, but that's the gist of it.

## Installation

1. Before running the script you'll need to have ffmpeg installed and on your system path. You can get the latest release for your OS at this link:  
https://ffmpeg.zeranoe.com/builds/  
Make sure to get the GPL version, as LGPL builds don't include x264!

2. You'll also need to install the scripts requirements by running:  
`pip install -r requirements.txt`

## Usage

All the below instructions assume your current working directory is PlexWebTranscoder/

### Basic Usage

You can run the script with default settings by simply running:  
`python index.py`  
This will transcode any files in the input/ folder, storing the transcoded files in the output/ folder.

## TODO:
- flesh out readme
- split into multiple files
- test in bash (specifically color stuff & path autocomplete)
- path tab completion on Windows
- better prints/logging
- do subtitles need to be considered?
- add ability to convert audio to stereo, like with this command: `ffmpeg -i "input-file.mp4" -ac 2 -vcodec copy "output-file.mp4"`
- for wizard, ask question first, and don't mention default when explaining options
- store preferences in separate file
- combine discovery & normal modes (remove option, run discovery, then ask if you want to convert)
