the way i downloaded it: (2026-08-26)

python linkDownloader.py --delay 10 --output txtFiles\nsfw.txt
python linkDownloader.py --delay 5 --output txtFiles\media.txt --url "https://hanime.tv/browse/images?channels=media&size=96"
python linkDownloader.py --delay 5 --output txtFiles\furry.txt --url "https://hanime.tv/browse/images?channels=furry&size=96"
python linkDownloader.py --delay 5 --output txtFiles\futa.txt --url "https://hanime.tv/browse/images?channels=futa&size=96"
python linkDownloader.py --delay 5 --output txtFiles\yaoi.txt --url "https://hanime.tv/browse/images?channels=yaoi&size=96"
python linkDownloader.py --delay 5 --output txtFiles\yuri.txt --url "https://hanime.tv/browse/images?channels=yuri&size=96"
python linkDownloader.py --delay 5 --output txtFiles\traps.txt --url "https://hanime.tv/browse/images?channels=traps&size=96"
python linkDownloader.py --delay 5 --output txtFiles\irl-3d.txt --url "https://hanime.tv/browse/images?channels=irl-3d&size=96"

For final download you could use:
yt-dlp --batch-file txtFiles\nsfw-general.txt --download-archive hanimePicsArchive.txt --output "nsfw-general\%(title)s.%(ext)s"

to update:
python linkDownloader.py --delay 10 --output txtFiles\nsfw.txt --update