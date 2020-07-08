import argparse
import glob
# import logging
import os
from shutil import copyfile
import platform
import time

from colorama import deinit, Fore, init
import ffmpeg
if platform.system() == "Darwin":
    import readline
# elif platform.system() == "Windows":
#     from pyreadline import Readline
#     readline = Readline()

# logging.basicConfig()
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

# False: only transcode video files from current directory
# True: transcode video files from current directory and all subdirectories (except OUTPUT_DIRECTORY)
RECURSIVE = True
# False: put transcoded / copied files into OUTPUT_DIRECTORY
# True: put transcoded files into its original directory and DELETE original file
IN_PLACE_TRANSCODING = False
# False: run as normal, transcoding video files when necessary
# True: run in 'discovery mode', where video files that require transcoding are found,
#   and a report is generated with info on which files require transcoding and why
DISCOVERY_MODE = False

# directory to read from, defaulting to current directory
INPUT_DIRECTORY = "./input"
# directory where files will go if not transcoding in place
OUTPUT_DIRECTORY = "./output"
# desired output file video codec
OUTPUT_VIDEO_CODEC = 'h264'
# video codecs that don't require transcoding
ALLOWED_OUTPUT_VIDEO_CODECS = ['h264']
# desired output file audio codec
OUTPUT_AUDIO_CODEC = 'aac'
# audio codecs that don't require transcoding
ALLOWED_OUTPUT_AUDIO_CODECS = ['aac']
# desired output file type
OUTPUT_FILE_TYPE = 'mp4'
# file types that don't require transcoding if codec requirements are satisfied
ALLOWED_OUTPUT_FILE_TYPES = ['mp4', 'm4v', 'mkv']
# filetypes to automatically skip; this could get really long, but these are the main ones for me
EXCLUDED_FILE_TYPES = ['py', 'txt', 'zip', 'rar', 'exe', 'srt', 'sub', 'jpg', 'jpeg', 'png', 'webp']

# log level for ffmpeg, which does the transcoding
FFMPEG_LOG_LEVEL = 'quiet'

discovery_mode_list = []


def output_banner():
    """Print out the fancy banner

    Prints out the big PLEXWEB ENCODER banner. Banner was generated using this site:
    http://patorjk.com/software/taag/#p=display&f=Ogre&t=plexweb%20transcoder
    with the selected font of Ogre, then a border was clumsily, manually placed around it.
    """

    print(Fore.CYAN)
    print("  _____________________________________________________________________________________________ ")
    print(" \\        _                         _       _                                     _            \\")
    print(" /  _ __ | | _____  ____      _____| |__   | |_ _ __ __ _ _ __  ___  ___ ___   __| | ___ _ __  /")
    print(" \\ | '_ \\| |/ _ \\ \\/ /\\ \\ /\\ / / _ \\ '_ \\  | __| '__/ _` | '_ \\/ __|/ __/ _ \\ / _` |/ _ \\ '__| \\")
    print(" / | |_) | |  __/>  <  \\ V  V /  __/ |_) | | |_| | | (_| | | | \\__ \\ (_| (_) | (_| |  __/ |    /")
    print(" \\ | .__/|_|\\___/_/\\_\\  \\_/\\_/ \\___|_.__/   \\__|_|  \\__,_|_| |_|___/\\___\\___/ \\__,_|\\___|_|    \\")
    print(" / |_|                                                                                         /")
    print(" \\_____________________________________________________________________________________________\\")
    print(Fore.RESET)


def plurality_check(int_to_check):
    """Check if a number is 1 for pluralizing output

    Check whether the given number is 1, and return a blank string
    if it isn't and 's' if it is. This can e.g. be stuck in print lines
    to conditionally pluralize nouns.

    Parameters
    ----------
    int_to_check : number
        Number to check for plurality

    Returns
    -------
    string
        either an empty string or 's'
    """

    return '' if int_to_check == 1 else 's'


def seconds_to_string(time_seconds):
    """Convert a number of seconds into a string of human-readable time

    Starting with a number of seconds, return a string of how many
    hours, minutes and seconds it equals.
    For example, 3602 will return "1 hour, 2 seconds".

    Parameters
    ----------
    time_seconds : number
        Number of seconds

    Returns
    -------
    string
        human-readable length of time in hours, minutes, and seconds
    """

    time_seconds = round(time_seconds)
    time_minutes = 0
    time_hours = 0
    if (time_seconds >= 60):
        time_minutes = time_seconds // 60
        time_seconds %= 60
        if (time_minutes >= 60):
            time_hours = time_minutes // 60
            time_minutes %= 60

    output_text = ""
    if (time_hours > 0):
        output_text += f"{time_hours} hour{plurality_check(time_hours)}"
    if (time_minutes > 0):
        if (output_text != ""):
            output_text += ", "
        output_text += f"{time_minutes} minute{plurality_check(time_minutes)}"
    if (time_seconds > 0):
        if (output_text != ""):
            output_text += ", "
        output_text += f"{time_seconds} second{plurality_check(time_seconds)}"

    return output_text if output_text != "" else "0 seconds"


def get_current_codecs(input_path):
    """Find the current video and audio codec of a file

    Determine what video and audio codecs the file at the given path
    is using. If the file has more than one audio or video stream,
    it will return the codec of the first. If it is missing either,
    or is not a file format which can be probed this way,
    it will return None for that codec or both.

    Parameters
    ----------
    input_path : string
        full path of the input file, including file name and type

    Returns
    -------
    string
        a string describing the video codec of the file at the given path
    string
        a string describing the audio codec of the file at the given path
    """

    try:
        probe_result = ffmpeg.probe(input_path)
        video_codec = None
        audio_codec = None
        for stream in probe_result['streams']:
            if not video_codec and stream['codec_type'] == 'video':
                video_codec = stream['codec_name']
            if not audio_codec and stream['codec_type'] == 'audio':
                audio_codec = stream['codec_name']
            if video_codec and audio_codec:
                break
        return video_codec, audio_codec
    except (Exception):
        return None, None


def transcoding_is_necessary(file_info):
    """Check if transcoding is necessary for a file

    Determine whether transcoding is necessary for a given file.
    If it is, return True; if it isn't, copy the file to the output
    directory (if not transcoding in place) and then return False.

    Parameters
    ----------
    file_info : dict
        Info about this file with keys:
        file_name: name of the input file, excluding file type
        file_type: type of the input file
        input_path: full path of the input file, including file name and type
        output_video_option: video codec transcoding option
        output_audio_option: audio codec transcoding option

    Returns
    -------
    bool
        a boolean describing if transcoding is necessary for this file
    """

    if (
        file_info['output_video_option'] == 'copy' and
        file_info['output_audio_option'] == 'copy' and
        file_info['file_type'] in ALLOWED_OUTPUT_FILE_TYPES
    ):
        if DISCOVERY_MODE:
            return False
        print(f" {Fore.GREEN}File doesn't need to be transcoded{Fore.RESET}")
        if not IN_PLACE_TRANSCODING:
            output_file = f'{OUTPUT_DIRECTORY}/{file_info["file_name"]}.{file_info["file_type"]}'
            if os.path.isfile(output_file):
                counter = 1
                error_start_text = f"{Fore.RED}File {Fore.CYAN}{output_file}{Fore.RED} already exists; {Fore.RESET}"
                while os.path.isfile(output_file):
                    output_file = f'{OUTPUT_DIRECTORY}/{file_info["file_name"]}-{counter}.{file_info["file_type"]}'
                    counter += 1
                print(f" {error_start_text}{Fore.RED}instead copying to {Fore.CYAN}{output_file}{Fore.RESET}")
            copyfile(file_info['input_path'], output_file)
        return False
    return True


def get_output_file(directory_path, file_name):
    """Get the output file path, name, and type

    Determine the output file path, name, and type. Type is set
    by a static variable, path depends on if transcoding in place is enabled,
    name also depends on that as well as whether a file already exists
    with the given path/name/type combination.

    Parameters
    ----------
    directory_path : string
        path of the input file, excluding file name and type
    file_name : string
        name of the input file, excluding file type

    Returns
    -------
    string
        a string which dictates the output file path, name, and type.
        e.g. 'path/to/file.mp4'
    """

    if IN_PLACE_TRANSCODING:
        output_file = f'{directory_path}/{file_name}-TEMP.{OUTPUT_FILE_TYPE}'
        counter = 1
        while os.path.isfile(output_file):
            output_file = f'{directory_path}/{file_name}-TEMP-{counter}.{OUTPUT_FILE_TYPE}'
            counter += 1
    else:
        output_file = f'{OUTPUT_DIRECTORY}/{file_name}.{OUTPUT_FILE_TYPE}'

        counter = 1
        while os.path.isfile(output_file):
            output_file = f'{OUTPUT_DIRECTORY}/{file_name}-{counter}.{OUTPUT_FILE_TYPE}'
            counter += 1
    return output_file


def get_codec_options(file_info):
    """Get codec options to use for transcoding a given file

    Determine what video and audio codec options to use for transcoding
    a given file. An option will either be the name of the codec, set in
    a static variable, or 'copy' if the file already uses that codec.

    Parameters
    ----------
    file_info : dict
        Info about this file with keys:
        input_path: full path of the input file, including file name and type
        input_video: video codec of the input video
        input_audio: audio codec of the input video

    Returns
    -------
    string
        a string which dictates the video codec transcoding option
    string
        a string which dictates the audio codec transcoding option
    """

    if not DISCOVERY_MODE:
        print(f" {Fore.GREEN}File {Fore.CYAN}{file_info['input_path']}{Fore.GREEN} has {Fore.YELLOW}{file_info['input_video']}{Fore.GREEN} video and {Fore.YELLOW}{file_info['input_audio']}{Fore.GREEN} audio{Fore.RESET}")

    output_video_option = 'copy' if file_info['input_video'] in ALLOWED_OUTPUT_VIDEO_CODECS else OUTPUT_VIDEO_CODEC
    output_audio_option = 'copy' if file_info['input_audio'] in ALLOWED_OUTPUT_AUDIO_CODECS else OUTPUT_AUDIO_CODEC

    return output_video_option, output_audio_option


def transcode_video(file_info):
    """Transcode the given video using given codec options

    Transcode the given file using the given codec options. If not
    transcoding in place, transcode directly to the output path; otherwise,
    transcode in the same directory as the input file with a temporary name,
    then delete the input file and rename the output with the input's name.

    Parameters
    ----------
    file_info : dict
        Info about this file with keys:
        directory_path: path of the input file, excluding file name and type
        file_name: name of the input file, excluding file type
        input_path: full path of the input file, including file name and type
        output_video_option: video codec transcoding option
        output_audio_option: audio codec transcoding option

    Returns
    -------
    bool
        a boolean describing if transcoding occurred and was successful
    """

    output_file = get_output_file(file_info['directory_path'], file_info['file_name'])

    stream = ffmpeg.input(file_info['input_path'])
    # -stats has progress show even when log level is non-verbose
    stream = ffmpeg.output(
        stream,
        output_file,
        vcodec=file_info['output_video_option'],
        acodec=file_info['output_audio_option'],
        loglevel=FFMPEG_LOG_LEVEL
    ).global_args('-stats', '-n')
    try:
        ffmpeg.run(stream)
    except (Exception):
        print(f" {Fore.RED}File {Fore.CYAN}{output_file}{Fore.RED} already exists; skipping transcoding{Fore.RESET}")
        # Exception will occur if you choose not to overwrite a file
        return False

    if IN_PLACE_TRANSCODING:
        # delete input file and rename output file
        os.remove(file_info['input_path'])
        # This could result in a file with the same name as the input
        #   but the same type as output being overwritten
        os.rename(output_file, f'{file_info["directory_path"]}/{file_info["file_name"]}.{OUTPUT_FILE_TYPE}')

    return True


def split_file_name_type(file_name_and_type):
    """Split a file name and type combination

    Split a file name and type combination (e.g. 'awesome_movie.mp4')
    into a separate file name ('awesome_movie') and type ('mp4')

    Parameters
    ----------
    file_name_and_type : string
        Combination filename and type (e.g. 'awesome_movie.mp4')

    Returns
    -------
    string
        name of the file, excluding file type (e.g. 'awesome_movie')
    string
        type of the file (e.g. 'mp4')
    """

    file_name_and_type_list = file_name_and_type.split('.')
    file_name = '.'.join(file_name_and_type_list[0:-1])
    file_type = file_name_and_type_list[-1].lower()
    return file_name, file_type


def get_files():
    """Get a list of directories and files to try to transcode

    Walk the current directory (and optionally subdirectories,
    based on static variable) and produce a list of dictionaries,
    each containing the name of a directory and a list of filenames
    in that directory

    Returns
    -------
    list
        list of dictionaries, each with keys:
        directory_path: path to directory
        file_names: list of files in this directory
    """

    directory_list = []
    for (dirpath, dirnames, filenames) in os.walk(INPUT_DIRECTORY):
        # don't walk output directory or subdirectories
        if (OUTPUT_DIRECTORY in dirpath):
            continue

        current_directory_dict = {
            "directory_path": dirpath,
            "file_names": filenames
        }
        directory_list.append(current_directory_dict)

        # if not transcoding subdirectories, finish after first pass (current directory)
        if not RECURSIVE:
            break
    return directory_list


def add_discovery_output(file_info):
    """Appends a string about the given file to the discovery list

    Discover what about the current file causes it to require transcoding,
    and append a string to the global discovery_mode_list describing
    the file and the problem with it, to be printed later.

    Parameters
    ----------
    file_info : dict
        Info about this file with keys:
        input_path: full path of the input file, including file name and type
        input_video: video codec of the input video
        input_audio: audio codec of the input video
        file_type: type of the input file
    """

    discovery_output = f" File {Fore.CYAN}{file_info['input_path']}{Fore.RESET}"

    issues = ""
    if file_info['input_video'] not in ALLOWED_OUTPUT_VIDEO_CODECS:
        issues += f" has {Fore.RED}{file_info['input_video']} video{Fore.RESET}"
    if file_info['input_audio'] not in ALLOWED_OUTPUT_AUDIO_CODECS:
        if issues != "":
            issues += " and"
        issues += f" has {Fore.RED}{file_info['input_audio']} audio{Fore.RESET}"
        pass
    if file_info['file_type'] not in ALLOWED_OUTPUT_FILE_TYPES:
        if issues != "":
            issues += " and"
        issues += f" is in {Fore.RED}{file_info['file_type']} format{Fore.RESET}"
        pass

    discovery_output += issues
    discovery_mode_list.append(discovery_output)


def process_single_file(single_file, directory_path):
    """Process a single file (check codecs, possibly transcode)

    Access the given file, determine if it is a video and what its current
    codecs are, and then (if transcoding is necessary) store a line to be
    printed in the report (if in discovery mode) or transcode the file to use
    the necessary video code, audio codec, and file format.

    Parameters
    ----------
    single_file : string
        Combination filename and type (e.g. 'awesome_movie.mp4')
    directory_path : string
        Path to the directory in which single_file resides

    Returns
    -------
    bool
        boolean signifying whether the input file was transcoded successfully.
        A False response means either transcoding failed or was not required.
    """

    file_name, file_type = split_file_name_type(single_file)

    if file_type in EXCLUDED_FILE_TYPES:
        return False

    if not DISCOVERY_MODE:
        print()

    file_info = {
        'directory_path': directory_path,
        'file_name': file_name,
        'file_type': file_type,
        'input_path': f'{directory_path}/{file_name}.{file_type}'
    }

    input_video, input_audio = get_current_codecs(file_info['input_path'])
    file_info.update({
        'input_video': input_video,
        'input_audio': input_audio
    })

    if not file_info['input_video'] or not file_info['input_audio']:
        print(f" {Fore.RED}File {Fore.CYAN}{file_info['input_path']}{Fore.RED} is missing video and/or audio streams; likely not a video file{Fore.RESET}")
        return False

    output_video_option, output_audio_option = get_codec_options(file_info)
    file_info.update({
        'output_video_option': output_video_option,
        'output_audio_option': output_audio_option
    })

    if not transcoding_is_necessary(file_info):
        return False

    if DISCOVERY_MODE:
        add_discovery_output(file_info)
        return False

    transcoding_success = transcode_video(file_info)
    return transcoding_success


def complete(text, state):
    """"Completer function for directory autocomplete on macOS"""
    return (glob.glob(text+'*')+[None])[state]


def await_existing_directory_input(prompt_string, default='.'):
    """Accept user directory path input

    Print out the prompt string, then await the user to input directory.
    If the input is not a valid existing directory, the user is reprompted.
    If no characters are input by the user, the default is used.

    Parameters
    ----------
    prompt_string : string
        The text with which to prompt the user (a question)
    default : string (optional)
        Default directory if user hits return without typing characters

    Returns
    -------
    string
        The user's response to the question
    """

    print(f" {prompt_string} (default is {default})")
    while True:
        # autocomplete paths on macOS
        if platform.system() == 'Darwin':
            readline.set_completer_delims(' \t\n;')
            readline.parse_and_bind('tab: complete')
            readline.set_completer(complete)
        response = input('   ')

        if os.path.exists(response):
            return response
        elif not response:
            return default
        else:
            print(f" Invalid path. Please retry: (default is {default})")


def await_string_list_input(prompt_string, default):
    """Accept user text list input

    Print out the prompt string, then await the user to input text.
    If text is entered, the user is reprompted to either add another
    value or return the current list. The default is used when no
    characters are input by the user during the first prompt.

    Parameters
    ----------
    prompt_string : string
        The text with which to prompt the user (a question)
    default : list (optional)
        Default list if user hits return without typing characters

    Returns
    -------
    list of strings
        The user's response to the question
    """

    default_output = f"(default is {default})"
    print(f" {prompt_string} {default_output}")
    while True:
        response = input('   ')
        user_list = []
        if response:
            while response:
                user_list.append(response)
                print(f" Enter another value to add to the list, or press return to save current list of {user_list}:")
                response = input('   ')
            return user_list
        else:
            return default


def await_string_input(prompt_string, default=None):
    """Accept user text input

    Print out the prompt string, then await the user to input text.
    If a default is provided, it is used when no characters are
    input by the user; otherwise, the user is re-prompted

    Parameters
    ----------
    prompt_string : string
        The text with which to prompt the user (a question)
    default : string (optional)
        Default answer if user hits return without typing characters

    Returns
    -------
    string
        The user's response to the question
    """

    default_output = "(response is required)"
    if default:
        default_output = f"(default is {default})"
    print(f" {prompt_string} {default_output}")
    while True:
        response = input('   ')
        if response:
            return response
        elif default and not response:
            return default
        else:
            print(f" Response is required. Please retry: {default_output}")


def await_bool_input(prompt_string, default=False):
    """Accept user input of yes or no

    Print out the prompt string, then await user input of yes or no,
    with the given default for when no characters are input. Retry
    on invalid input

    Parameters
    ----------
    prompt_string : string
        The text with which to prompt the user (yes or no question)
    default : bool (optional)
        Default answer if user hits return without typing characters

    Returns
    -------
    bool
        The user's response to the question
    """

    options_string = 'y/[n]'
    if default is True:
        options_string = '[y]/n'
    print(f" {prompt_string} {options_string}")
    while True:
        response = input('   ').lower()
        if response == 'n' or response == 'no' or (not response and default is False):
            return False
        elif response == 'y' or response == 'yes' or (not response and default is True):
            return True
        else:
            print(f" Invalid input. Please retry: {options_string}")


def run_wizard():
    """Run a wizard to set options before running continuing with the script

    Output a series of questions, set variables with the user's responses
    which dictate how the script will run
    """

    global RECURSIVE
    global IN_PLACE_TRANSCODING
    global DISCOVERY_MODE

    global INPUT_DIRECTORY
    global OUTPUT_DIRECTORY
    global OUTPUT_VIDEO_CODEC
    global ALLOWED_OUTPUT_VIDEO_CODECS
    global OUTPUT_AUDIO_CODEC
    global ALLOWED_OUTPUT_AUDIO_CODECS
    global OUTPUT_FILE_TYPE
    global ALLOWED_OUTPUT_FILE_TYPES
    global EXCLUDED_FILE_TYPES

    # record defaults to check for changes later
    default_recursive = RECURSIVE
    default_in_place_trancoding = IN_PLACE_TRANSCODING
    default_discovery_mode = DISCOVERY_MODE

    default_input_directory = INPUT_DIRECTORY
    default_output_directory = OUTPUT_DIRECTORY
    default_output_video_codec = OUTPUT_VIDEO_CODEC
    default_allowed_output_video_codecs = ALLOWED_OUTPUT_VIDEO_CODECS
    default_output_audio_codec = OUTPUT_AUDIO_CODEC
    default_allowed_output_audio_codecs = ALLOWED_OUTPUT_AUDIO_CODECS
    default_output_file_type = OUTPUT_FILE_TYPE
    default_allowed_output_file_types = ALLOWED_OUTPUT_FILE_TYPES
    default_excluded_file_types = EXCLUDED_FILE_TYPES

    current_question = 1
    command_flag_arguments = ' -'
    command_value_arguments = ''

    # bool arguments
    input_directory_prompt = f"{current_question}. {Fore.CYAN}What is the path to the input directory?{Fore.RESET}"
    INPUT_DIRECTORY = await_existing_directory_input(input_directory_prompt, INPUT_DIRECTORY)
    current_question += 1
    if (INPUT_DIRECTORY != default_input_directory):
        command_value_arguments += f' -id "{INPUT_DIRECTORY}"'

    discovery_prompt = f"{current_question}. This script can be run in discovery mode in order to generate a report on\n which files require transcoding and why, without doing any actual transcoding.\n {Fore.CYAN}Run in discovery mode?{Fore.RESET}"
    DISCOVERY_MODE = await_bool_input(discovery_prompt, DISCOVERY_MODE)
    current_question += 1
    if (DISCOVERY_MODE != default_discovery_mode):
        command_flag_arguments += 'd'

    if not DISCOVERY_MODE:
        in_place_prompt = f"{current_question}. By default, this script saves a transcoded file to a specific output directory.\n Alternatively, you can choose to save the file to its source directory, deleting the source file.\n {Fore.CYAN}Do you wish to save to source directories and delete source files?{Fore.RESET}"
        IN_PLACE_TRANSCODING = await_bool_input(in_place_prompt, IN_PLACE_TRANSCODING)
        current_question += 1
        if (IN_PLACE_TRANSCODING != default_in_place_trancoding):
            command_flag_arguments += 'p'

    if IN_PLACE_TRANSCODING or DISCOVERY_MODE:
        recursive_prompt = f"{current_question}. {Fore.CYAN}Run for input directory's subdirectories?{Fore.RESET}"
    else:
        recursive_prompt = f"{current_question}. {Fore.CYAN}Run for input directory's subdirectories (excluding the output directory)?{Fore.RESET}"
    RECURSIVE = await_bool_input(recursive_prompt, RECURSIVE)
    current_question += 1
    if (RECURSIVE != default_recursive):
        command_flag_arguments += 'n'

    # string arguments
    if not IN_PLACE_TRANSCODING and not DISCOVERY_MODE:
        output_directory_prompt = f"{current_question}. {Fore.CYAN}What is the path to the output directory?{Fore.RESET} If it does not exist,\n it will be created."
        OUTPUT_DIRECTORY = await_string_input(output_directory_prompt, OUTPUT_DIRECTORY)
        current_question += 1
        if (OUTPUT_DIRECTORY != default_output_directory):
            command_value_arguments += f' -od "{OUTPUT_DIRECTORY}"'

    file_codec_prompt = f"{current_question}. The default settings for file type / codecs are designed to allow direct play\n to the Plex web app. {Fore.CYAN}Do you wish to change file type / codec settings?{Fore.RESET}"
    ask_file_codec_questions = await_bool_input(file_codec_prompt)
    current_question += 1

    if ask_file_codec_questions:

        allowed_vcodecs_prompt = f"{current_question}. {Fore.CYAN}What are the allowed video codecs?{Fore.RESET} Files that use any of these codecs\n won't require video transcoding."
        ALLOWED_OUTPUT_VIDEO_CODECS = await_string_list_input(allowed_vcodecs_prompt, ALLOWED_OUTPUT_VIDEO_CODECS)
        current_question += 1
        if (ALLOWED_OUTPUT_VIDEO_CODECS != default_allowed_output_video_codecs):
            formated_for_output = ' '.join(ALLOWED_OUTPUT_VIDEO_CODECS)
            command_value_arguments += f' -avc "{formated_for_output}"'

        output_vcodec_prompt = f"{current_question}. {Fore.CYAN}What is the desired video codec?{Fore.RESET} Files that require video transcoding\n will use this codec."
        OUTPUT_VIDEO_CODEC = await_string_input(output_vcodec_prompt, OUTPUT_VIDEO_CODEC)
        current_question += 1
        if (OUTPUT_VIDEO_CODEC != default_output_video_codec):
            command_value_arguments += f' -vc "{OUTPUT_VIDEO_CODEC}"'

        allowed_acodecs_prompt = f"{current_question}. {Fore.CYAN}What are the allowed audio codecs?{Fore.RESET} Files that use any of these codecs\n won't require audio transcoding."
        ALLOWED_OUTPUT_AUDIO_CODECS = await_string_list_input(allowed_acodecs_prompt, ALLOWED_OUTPUT_AUDIO_CODECS)
        current_question += 1
        if (ALLOWED_OUTPUT_AUDIO_CODECS != default_allowed_output_audio_codecs):
            formated_for_output = ' '.join(ALLOWED_OUTPUT_AUDIO_CODECS)
            command_value_arguments += f' -aac "{formated_for_output}"'

        output_acodec_prompt = f"{current_question}. {Fore.CYAN}What is the desired audio codec?{Fore.RESET} Files that require audio transcoding\n will use this codec."
        OUTPUT_AUDIO_CODEC = await_string_input(output_acodec_prompt, OUTPUT_AUDIO_CODEC)
        current_question += 1
        if (OUTPUT_AUDIO_CODEC != default_output_audio_codec):
            command_value_arguments += f' -ac "{OUTPUT_AUDIO_CODEC}"'

        allowed_file_types_prompt = f"{current_question}. {Fore.CYAN}What are the allowed file types?{Fore.RESET} Files that use any of these file types\n won't require transcoding if the codec requirements are also met."
        ALLOWED_OUTPUT_FILE_TYPES = await_string_list_input(allowed_file_types_prompt, ALLOWED_OUTPUT_FILE_TYPES)
        current_question += 1
        if (ALLOWED_OUTPUT_FILE_TYPES != default_allowed_output_file_types):
            formated_for_output = ' '.join(ALLOWED_OUTPUT_FILE_TYPES)
            command_value_arguments += f' -aft "{formated_for_output}"'

        output_file_type_prompt = f"{current_question}. {Fore.CYAN}What is the desired file type?{Fore.RESET} Files that require transcoding\n will use this type."
        OUTPUT_FILE_TYPE = await_string_input(output_file_type_prompt, OUTPUT_FILE_TYPE)
        current_question += 1
        if (OUTPUT_FILE_TYPE != default_output_file_type):
            command_value_arguments += f' -ft "{OUTPUT_FILE_TYPE}"'

        excluded_file_types_prompt = f"{current_question}. {Fore.CYAN}What are the excluded file types?{Fore.RESET} Files that use any of these file types\n won't be considered for transcoding."
        EXCLUDED_FILE_TYPES = await_string_list_input(excluded_file_types_prompt, EXCLUDED_FILE_TYPES)
        current_question += 1
        if (EXCLUDED_FILE_TYPES != default_excluded_file_types):
            formated_for_output = ' '.join(EXCLUDED_FILE_TYPES)
            command_value_arguments += f' -eft "{formated_for_output}"'

    command_to_rerun = f'python transcode-video.py{command_flag_arguments}{command_value_arguments}'
    print(" Running the following command will rerun the script with these same settings:")
    print(f' {Fore.GREEN}{command_to_rerun}{Fore.RESET}')


def process_arguments():
    """Process arguments provided when running the script"""

    global RECURSIVE
    global IN_PLACE_TRANSCODING
    global DISCOVERY_MODE

    global INPUT_DIRECTORY
    global OUTPUT_DIRECTORY
    global OUTPUT_VIDEO_CODEC
    global ALLOWED_OUTPUT_VIDEO_CODECS
    global OUTPUT_AUDIO_CODEC
    global ALLOWED_OUTPUT_AUDIO_CODECS
    global OUTPUT_FILE_TYPE
    global ALLOWED_OUTPUT_FILE_TYPES
    global EXCLUDED_FILE_TYPES

    parser = argparse.ArgumentParser(description='Transcode video files for use in the Plex web player', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    flag_argument_group = parser.add_argument_group('optional flag arguments')

    # arguments set by the wizard should override any conflicting arguments
    flag_argument_group.add_argument('-w', '--wizard', action='store_true', help="run the script's wizard")

    recursive_action = 'store_false' if not RECURSIVE else 'store_true'
    flag_argument_group.add_argument('-n', '--nonrecursive', action=recursive_action, help="only run for input directory, not its subdirectories")

    inplace_action = 'store_false' if IN_PLACE_TRANSCODING else 'store_true'
    flag_argument_group.add_argument('-p', '--inplace', action=inplace_action, help="transcode files in-place (deleting original) instead of saving to output directory")

    discovery_action = 'store_false' if DISCOVERY_MODE else 'store_true'
    flag_argument_group.add_argument('-d', '--discovery', action=discovery_action, help="generate report about files that need transcoding but don't transcode files")

    value_argument_group = parser.add_argument_group('optional value arguments')

    value_argument_group.add_argument('-id', '--inputdirectory', default=INPUT_DIRECTORY, help="directory to check for files that need transcoding")

    value_argument_group.add_argument('-od', '--outputdirectory', default=OUTPUT_DIRECTORY, help="directory where transcoded/copied files will be saved (if in-place transcoding is off)")

    value_argument_group.add_argument('-vc', '--videocodec', default=OUTPUT_VIDEO_CODEC, help="video codec to use for output files")

    value_argument_group.add_argument('-avc', '--allowedvideocodecs', default=ALLOWED_OUTPUT_VIDEO_CODECS, nargs='+', help="space-separated list of video codecs that don't require transcoding")

    value_argument_group.add_argument('-ac', '--audiocodec', default=OUTPUT_AUDIO_CODEC, help="audio codec to use for output files")

    value_argument_group.add_argument('-aac', '--allowedaudiocodecs', default=ALLOWED_OUTPUT_AUDIO_CODECS, nargs='+', help="space-separated list of audio codecs that don't require transcoding")

    value_argument_group.add_argument('-ft', '--filetype', default=OUTPUT_FILE_TYPE, help="file type to use for output files")

    value_argument_group.add_argument('-aft', '--allowedfiletypes', default=ALLOWED_OUTPUT_FILE_TYPES, nargs='+', help="space-separated list of file types that don't require transcoding if codec requirements are met")

    value_argument_group.add_argument('-eft', '--excludedfiletypes', default=EXCLUDED_FILE_TYPES, nargs='+', help="space-separated list of file types that should be automatically skipped (e.g. non video types)")

    args = parser.parse_args()

    RECURSIVE = not args.nonrecursive
    IN_PLACE_TRANSCODING = args.inplace
    DISCOVERY_MODE = args.discovery

    INPUT_DIRECTORY = args.inputdirectory
    OUTPUT_DIRECTORY = args.outputdirectory
    OUTPUT_VIDEO_CODEC = args.videocodec
    ALLOWED_OUTPUT_VIDEO_CODECS = args.allowedvideocodecs
    OUTPUT_AUDIO_CODEC = args.audiocodec
    ALLOWED_OUTPUT_AUDIO_CODECS = args.allowedaudiocodecs
    OUTPUT_FILE_TYPE = args.filetype
    ALLOWED_OUTPUT_FILE_TYPES = args.allowedfiletypes
    EXCLUDED_FILE_TYPES = args.excludedfiletypes

    if (args.wizard):
        run_wizard()


def main():
    start_time = time.time()
    # filter ANSI escape sequences on windows
    init()

    output_banner()

    process_arguments()

    total_files_count = 0
    transcoded_videos_count = 0
    if not IN_PLACE_TRANSCODING and not DISCOVERY_MODE:
        try:
            os.makedirs(OUTPUT_DIRECTORY)
        except (Exception):
            pass

    directory_list = get_files()

    for directory in directory_list:
        for single_file in directory['file_names']:
            # reverse backslashes on windows
            directory_path = directory['directory_path'].replace('\\', '/')

            file_was_transcoded = process_single_file(single_file, directory_path)

            total_files_count += 1
            print(f" Processing files! {Fore.YELLOW}{total_files_count} files{Fore.RESET} checked so far...", end='\r')

            if file_was_transcoded:
                transcoded_videos_count += 1

    elapsed_time = time.time() - start_time
    print(f"\n {Fore.CYAN}Script ran for {Fore.YELLOW}{seconds_to_string(elapsed_time)}{Fore.RESET}")

    if DISCOVERY_MODE:
        print(f"\n {Fore.YELLOW}{total_files_count} file{plurality_check(total_files_count)}{Fore.CYAN} checked{Fore.RESET}")
        discovered_count = len(discovery_mode_list)
        print(f"\n {Fore.GREEN}Found {Fore.YELLOW}{discovered_count} file{plurality_check(discovered_count)}{Fore.GREEN} requiring transcoding{'!' if discovered_count == 0 else ':'}{Fore.RESET}")
        for line in discovery_mode_list:
            print(line)
    else:
        print(f"\n Transcoded {Fore.YELLOW}{transcoded_videos_count} video{plurality_check(transcoded_videos_count)}{Fore.RESET}")

    # stop filtering ANSI escape sequences on windows
    deinit()


if __name__ == '__main__':
    main()
