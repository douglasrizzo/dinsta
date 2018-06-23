#!/usr/bin/env python3.6

import argparse
import os
from datetime import datetime
from shutil import copyfile, rmtree

import numpy as np
from PIL import Image, ImageChops
from instalooter.looters import ProfileLooter
from instalooter.pbar import TqdmProgressBar
from skimage.io import imread
from skimage.measure import compare_ssim
from skimage.transform import resize
from tqdm import tqdm
from multiprocessing import Pool


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


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

    looter = ProfileLooter(username, template=stripped_username + '_{likescount}_{date}_{id}')

    try:
        if not only_videos:
            looter.download_pictures(destination=path, pgpbar_cls=TqdmProgressBar, dlpbar_cls=TqdmProgressBar)
        if videos or only_videos:
            looter.download_videos(destination=path, pgpbar_cls=TqdmProgressBar, dlpbar_cls=TqdmProgressBar)
    except RuntimeError as e:
        print(e.what())

def list_dirs(paths):
    """Lists all the directories inside the given path. If a list is passed, the function iterates through every element and treats each one as a path inside the filesystem.

    :param paths:
    :returns: A list containing the absolute path to all directories inside the path or paths passed."""
    dirs = set()
    # create directory list
    for arg in set(paths):
        # expand argument if necessary
        if arg.endswith('/*'):
            for d in sorted(os.listdir(arg)):
                if os.path.isdir(d):
                    dirs.add(d)

        else:
            if os.path.isdir(arg):
                dirs.add(arg)
    return dirs


def list_images(dirs):
    """Lists all image files in a given directory or list of directories.

    :param dirs: a string with the path of a directory or a list of string with many paths.
    :returns: a list with the absolute paths of all image files inside the given directories."""
    # create list with image paths
    files = []

    # if a single string is passed, create a list of 1 element
    if type(dirs) == str:
        dirs = [dirs]

    for arg in sorted(dirs):
        # remove / at the end of arg if it comes with it
        while arg.endswith('/'):
            arg = arg[:-1]

        files += [
            arg + '/' + f for f in sorted(os.listdir(arg))
            if f.endswith('.jpg') or f.endswith('.png')
        ]

    return files


def trim_single_image(filepath):
    try:
        im = Image.open(filepath)
        bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
        diff = ImageChops.difference(im, bg)
        diff = ImageChops.add(diff, diff, 2.0, -100)
        bbox = diff.getbbox()
        if bbox:
            bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            im_area = im.size[0] * im.size[1]
            bbox_proportion = bbox_area / im_area
            if bbox_proportion < .999:
                directory = os.path.dirname(os.path.abspath(filepath))
                new_image = os.path.basename(filepath)
                # new_image, file_extension = os.path.splitext(new_image)
                new_image_name = directory + '/' + new_image
                im.crop(bbox).save(new_image_name)
    except:
        print('Could not load {}'.format(filepath))


def remove_borders(dirs):
    """Removes monochromatic borders from pictures. Borders are detected by getting the color of the pixel in position (0,0) of the image, tracing a bounding box around the image using the extracted color as a threshold and cropping the outside of the bounding box.

    Images are overwritten after being cropped.

    :param dirs: a string or list of strings containing all directories where images should be processed."""

    if type(dirs) == str:
        files = list_images(dirs)
    else:
        files = list_images(list_dirs(dirs))

    with Pool(os.cpu_count()) as pool:
        # how to make a progressbar when using multiprocessing
        # for some reason the cast to list() is necessary,
        # as well as passing file size
        list(
            tqdm(
                pool.imap(trim_single_image, files),
                total=len(files),
                desc="Trimming borders"))

    # for x in tqdm(files, desc='Trimming borders'):


def load_images(files, size=None, gray=False):
    """Loads a set of image files inside numpy.ndarray objects. Optionally, all images may be loaded in grayscale and resized to a standard size.

    :param files: a list of strings containing the path to the image files.
    :param size: a tuple containing the (x, y) dimensions images should be resized to.
    :param gray: whether to load images in grayscale or not.
    :returns: a list of tuples, where tuple[0] contains the path of the image and tuple[1] contains a numpy.ndarray object with the loaded image."""
    # progress bar for image loading procedure
    for x in tqdm(range(len(files)), desc='Loading images'):
        # grayscale and resize the images
        img = imread(files[x], asgray=gray)
        if size is not None:
            img = resize(img, size)
        files[x] = (files[x], img)

    return files


def set_dates(directory):
    """Sets the creation and modification dates of the scraped files to the dates they were posted on Instagram.
    Dates are collected from the file name, if the files have been scraped by using this script.

    :param directory: the directory where the image files are contained."""
    paths = list_images(directory)

    for path in paths:
        date = datetime.strptime(
            os.path.basename(path).split('_')[2], '%Y-%m-%d').timestamp()
        os.utime(path, (date, date))


def remove_duplicates(directory, threshold=.8):
    """Searches for duplicate files inside a directory and removes one of them.
    Image similarity is calculated by using skimage.measure.compare_ssim and images with similarity >= threshold are deleted.
    The deleted file is the one of lowest resolution.

    :param directory: the directory in which image files will be compared.
    :param threshold: the similarity threshold after which two images are considered equal."""
    files = load_images(list_images(directory), size=[100, 100], gray=True)
    files = sorted(files, key=lambda x: x[1][0, 0])
    pbar = tqdm(total=sum(range(len(files))), desc='Searching for duplicates')

    while len(files) > 0:
        p1, im1 = files[0]

        for p2, im2 in files[1:]:
            pbar.update()
            if abs(im1[0, 0] - im2[0, 0]) > .1:
                break
            if compare_ssim(im1, im2) > threshold:
                print('Found duplicate. Removing...')
                rgb1 = imread(p1)
                rgb2 = imread(p2)

                if rgb1.size > rgb2.size:
                    files[0] = (p2, im2)

                os.remove(p1)
                files = files[1:]
                pbar = tqdm(
                    total=sum(range(len(files))),
                    desc='Searching for duplicates')
                break
        files = files[1:]
        del p1, im1


def normalize_likes(directory):
    files = list_images(directory)
    zero_padding = len(
        str(max(int(os.path.basename(f).split('_')[1]) for f in files)))
    for f in files:
        bits = f.split('_')
        os.rename(f, bits[0] + '_' + bits[1].zfill(zero_padding) + '_' +
                  bits[2] + '_' + bits[3])


def sort_by_std(directory, stds=4, window_size=None):
    images = [
        i.split('_')[1:3] + [i] for i in os.listdir(directory)
        if i.endswith('.jpg')
    ]
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

        img_name = str(
            int(round(likes / window_avg, ndigits=3) * 1000)).zfill(6)

        if likes > window_avg * 1.5:
            copyfile(directory + '/' + filename,
                     directory + '/' + dir_name + '/' + img_name + '.jpg')


def process_dir(d, args):
    if args.duplicates:
        remove_duplicates(d)
    if args.borders:
        remove_borders(d)
    if args.sort:
        sort_by_std(d)
    if args.time:
        set_dates(d)
    if args.normalize_likes:
        normalize_likes(d)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Custom Instagram scraper created to automate repetitive tasks I '
                    'used to do manually when using other scrapers. It is a simple script that '
                    'uses instaLooter under the hood, so in case of any questions regarding '
                    'interactions with Instagram or custom options to do more stuff, check '
                    'instaLooter. It might have what you need.')
    parser.add_argument(
        'usernames', metavar='U', type=str, help='Instagram username (s)', nargs='+')
    parser.add_argument(
        '-d',
        '--duplicates',
        action='store_true',
        help='removes duplicate images, keeping the one with highest resolution'
    )
    parser.add_argument(
        '-b',
        '--borders',
        action='store_true',
        help='remove monochromatic image borders')
    parser.add_argument(
        '-t',
        '--time',
        action='store_true',
        help='set image creation and modification time to Instagram post time')
    parser.add_argument(
        '-s',
        '--sort',
        action='store_true',
        help='sort images by the std. dev. in like quantity')
    parser.add_argument(
        '-n',
        '--normalize_likes',
        action='store_true',
        help='adds zero-padding to number of likes in file names. Useful when sorting in image '
             'viewers that only have non-numerical sorting.')
    parser.add_argument(
        '-v',
        '--videos',
        action='store_true',
        help='download videos too')
    parser.add_argument(
        '-V',
        '--only_videos',
        action='store_true',
        help='download only videos')

    args = parser.parse_args()

    # get list of usernames
    users = args.usernames

    # scroll through usernames
    for i, user in enumerate(users):
        d = user

        # downloads files
        print('Downloading {0} {1}/{2}...'.format(user, i + 1, len(users)))
        download(user, videos=args.videos, only_videos=args.only_videos)
        # processes all additional command-line arguments as if the directory already existed
        process_dir(d, args)
