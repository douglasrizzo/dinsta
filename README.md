# Custom Instagram scraper

Custom Instagram scraper created to automate repetitive tasks I used to do manually when using other scrapers. It is a simple script that uses instalooter under the hood, so in case of any questions regarding interactions with Instagram or custom options to do more stuff, check instalooter. It might have what you need.

	positional arguments:
	  U                     Instagram username (s)

	optional arguments:
	  -h, --help            show this help message and exit
	  -d, --duplicates      removes duplicate images, keeping the one with highest
	                        resolution
	  -b, --borders         remove monochromatic image borders
	  -t, --time            set image creation and modification time to Instagram
	                        post time
	  -s, --sort            sort images by the std. dev. in like quantity
	  -n, --normalize_likes
	                        adds zero-padding to number of likes in file names.
	                        Useful when sorting in image viewers that only have
	                        non-numerical sorting.
	  -v, --videos          download videos too
	  -V, --only_videos     download only videos
