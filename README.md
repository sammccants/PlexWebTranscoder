# PlexWeb Transcoder

This script allows you to easily transcode batches of videos using ffmpeg. The original intention is to allow you to pre-transcode videos (before adding them to your Plex server) to the format and video/audio encodings that can be viewed in the PlexWeb app. This allows you to stream from a computationally weak server (like a Raspberry Pi) without having to worry about files failing to play because the server needs to transcode the video or audio and isn't powerful enough.

Though this is the reason for the creation of the script, and it dictates the default settings, you could also use the script to do simple batch transcoding of any video files, however you like.

Basically all it does is to walk through the files in the input folder, find any video files that don't match one of the video or audio encodings you want to allow, and transcodes them to the desired encodings. You can set options to change parts of its behavior, but that's the gist of it.

## Usage

todo


## TODO:
- flesh out readme
- split into multiple files
- test in bash (specifically color stuff & path autocomplete)
- path tab completion on Windows
- better prints/logging
- do subtitles need to be considered?
