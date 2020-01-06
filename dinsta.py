#!/usr/bin/env python3.6

import argparse
import os
from datetime import datetime
from shutil import copyfile, rmtree

import numpy as np
from instalooter.looters import ProfileLooter
from instalooter.pbar import TqdmProgressBar
from dodoimages.dodoimages import remove_duplicates, remove_borders
from imutils.paths import list_images


def download(username, path=None, videos=False, only_videos=False):
    """Downloads all pictures from a given Instagram profile using instaLooter and saves the files with a standard name to be used by other options of the looter.

    :param username: Instagram username
    :param path: directory where images will be saved
    :param videos: whether to download videos from the profile
    :param videos_only: download only the videos, ignore images
    """
    stripped_username = username.replace('_', '').strip()

    if stripped_username.startswith("."):
        stripped_username = stripped_username[1:]

    if path is None:
        path = username

    looter = ProfileLooter(username=username,
                get_videos=videos,
                videos_only=only_videos,
                add_metadata=True,
                template=stripped_username + '_{likescount}_{date}_{id}')\

    try:
        if not only_videos:
            looter.download_pictures(
                destination=path, pgpbar_cls=TqdmProgressBar, dlpbar_cls=TqdmProgressBar
            )
        if videos or only_videos:
            looter.download_videos(
                destination=path, pgpbar_cls=TqdmProgressBar, dlpbar_cls=TqdmProgressBar
            )
    except RuntimeError as e:
        if 'Query rate exceeded' in str(e):
            print(e)
            pass


def set_dates(paths):
    """Sets the creation and modification dates of the scraped files to the dates they were posted on Instagram.
    Dates are collected from the file name, if the files have been scraped by using this script."""
    for path in paths:
        _, file = os.path.split(path)
        date = datetime.strptime(file.split('_')[2], '%Y-%m-%d').timestamp()
        os.utime(path, (date, date))


def normalize_likes(files):
    zero_padding = len(str(max(int(os.path.basename(f).split('_')[1]) for f in files)))
    for f in files:
        bits = f.split('_')
        os.rename(f, bits[0] + '_' + bits[1].zfill(zero_padding) + '_' + bits[2] + '_' + bits[3])


def sort_by_std(directory, stds=4, window_size=None):
    images = [i.split('_')[1:3] + [i] for i in os.listdir(directory) if i.endswith('.jpg')]
    for i in images:
        i[0] = int(i[0])
        i[1] = datetime.strptime(i[1], '%Y-%m-%d')

    images = sorted(images, key=lambda x: x[1])

    dir_name = 'abs_std'

    if os.path.exists(directory + '/' + dir_name):
        rmtree(directory + '/' + dir_name)
    os.mkdir(directory + '/' + dir_name)

    if window_size is None:
        window_size = max(int(len(images) * .1), 50)

    # totalstd = np.std([x[0] for x in images])
    # totalavg = np.mean([x[0] for x in images])

    for i in range(len(images)):
        likes = images[i][0]
        filename = images[i][2]
        window_start = max(0, i - window_size)
        window_end = min(len(images), window_start + window_size)
        interval = [x[0] for x in images[window_start:window_end]]
        window_std = np.std(interval)
        window_avg = np.average(interval)
        window_threshold = window_std * stds

        img_name = str(int(round(likes / window_avg, ndigits=3) * 1000)).zfill(6)

        if likes > window_avg * 1.5:
            copyfile(
                directory + '/' + filename, directory + '/' + dir_name + '/' + img_name + '.jpg'
            )


def process_dir(d, args):
    images = list(list_images(d))
    if args.duplicates:
        remove_duplicates(images)
    if args.borders:
        remove_borders(images)
    if args.sort:
        sort_by_std(d)
    if args.time:
        set_dates(images)
    if args.normalize_likes:
        normalize_likes(images)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Custom Instagram scraper created to automate repetitive tasks I '
        'used to do manually when using other scrapers. It is a simple script that '
        'uses instaLooter under the hood, so in case of any questions regarding '
        'interactions with Instagram or custom options to do more stuff, check '
        'instaLooter. It might have what you need.'
    )
    parser.add_argument('usernames', metavar='U', type=str, help='Instagram username (s)', nargs='+')
    parser.add_argument('-d', '--duplicates', action='store_true', help='removes duplicate images, keeping the one with highest resolution')
    parser.add_argument(
        '-d',
        '--duplicates',
        action='store_true',
        help='removes duplicate images, keeping the one with highest resolution'
    )
    parser.add_argument(
        '-b', '--borders', action='store_true', help='remove monochromatic image borders'
    )
    parser.add_argument(
        '-t',
        '--time',
        action='store_true',
        help='set image creation and modification time to Instagram post time'
    )
    parser.add_argument(
        '-s', '--sort', action='store_true', help='sort images by the std. dev. in like quantity'
    )
    parser.add_argument(
        '-n',
        '--normalize_likes',
        action='store_true',
        help='adds zero-padding to number of likes in file names. Useful when sorting in image '
        'viewers that only have non-numerical sorting.'
    )
    parser.add_argument('-v', '--videos', action='store_true', help='download videos too')
    parser.add_argument('-V', '--only_videos', action='store_true', help='download only videos')

    args = parser.parse_args()

    # get list of usernames
    users = args.usernames

    # scroll through usernames
    for i, user in enumerate(users):

        # downloads files
        print('Downloading {0} {1}/{2}...'.format(user, i + 1, len(users)))
        download(user, videos=args.videos, only_videos=args.only_videos)
        d = os.path.abspath(user)
        # processes all additional command-line arguments as if the directory already existed
        process_dir(d, args)
