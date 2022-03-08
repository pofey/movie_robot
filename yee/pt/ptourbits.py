import cgi
import datetime
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from yee.core.stringutils import StringUtils
from yee.core.torrentmodels import Torrents, TorrentType, Torrent
from yee.movie.movieparser import MovieParser as mp
from yee.pt.nexusprogramsite import NexusProgramSite
from yee.pt.ptsiteparser import PTSiteParser


class PTOurbits(NexusProgramSite):
    def get_site(self):
        """
        返回pt站的网址
        :return:
        """
        return 'https://ourbits.club'

    def get_site_name(self):
        """
        这是pt网站的名称，确保唯一即可，集成到主程序时用作配置项
        :return:
        """
        return 'ourbits'

    def match_user(self, text):
        if text is None or text.strip() == '':
            return None
        soup = BeautifulSoup(text, features="lxml")
        match_login_user = soup.select('table[id="info_block"] tr td table tr td span a b')[0].get_text()
        print("user: %s" % match_login_user)
        if match_login_user:
            return StringUtils.trimhtml(match_login_user)
        else:
            return None

    def parse_torrents(self, text: str) -> Torrents:
        """
        通过返回的网页代码，解析列表页种子的所有信息
        :param text:
        :return:
        """
        soup = BeautifulSoup(text, features="lxml")
        search_result = []
        if not soup.find('table', class_="torrents"):
            return []

        torrents_rows = soup.find('table', class_="torrents").findAll('tr', recursive=False)
        if 0 == len(torrents_rows):
            torrents_rows = soup.find('table', class_="torrents").find("tbody").findAll('tr', recursive=False)[1:]
        for row in torrents_rows:
            t = Torrent()
            t.site_name = self.get_site_name()
            t.site = self.get_site()
            for i, item in enumerate(row.findAll('td', recursive=False)[:-1]):
                if i == 0:
                    t.primitive_type = item.select_one('a img')['title']
                    if "Movies" in t.primitive_type:
                        t.type = TorrentType.Movie
                        t.cate = TorrentType.Movie.value
                    elif t.primitive_type in ['TV-Pack', 'TV-Episode']:
                        t.type = TorrentType.Series
                        t.cate = TorrentType.Series.value
                    elif "Music" in t.primitive_type:
                        t.type = TorrentType.Music
                        t.cate = TorrentType.Music.value
                    elif "Documentary" in t.primitive_type:
                        t.type = TorrentType.Other
                        t.cate = '纪录片'
                    elif "Animation" in t.primitive_type:
                        t.type = TorrentType.Other
                        t.cate = '动漫'
                    else:
                        t.type = TorrentType.Other
                        t.cate = TorrentType.Other.value
                elif i == 1:
                    info = item.select('table tr td.embedded')[0]
                    a = info.select_one('a[title]')
                    t.name = str(a['title'])
                    t.id = re.findall('id=(\d+)', a['href'])[0]
                    if info.select_one('a[title]'):
                        deadline = info.select_one('a[title] ~ b span[title]')
                        if deadline:
                            t.free_deadline = datetime.datetime.strptime(deadline['title'], '%Y-%m-%d %H:%M:%S')
                        else:
                            t.free_deadline = datetime.datetime.max
                    subject = info.contents[-1]
                    t.subject = str(subject.string) if subject else ''
                    t.url = self.get_site() + '/download.php?id=' + t.id
                elif i == 3:
                    t.publish_time = datetime.datetime.strptime(item.select_one('span[title]')['title'],
                                                                '%Y-%m-%d %H:%M:%S')
                elif i == 4:
                    t.file_size = PTSiteParser.trans_unit_to_mb(float(item.contents[0]), str(item.contents[2].string))
                elif i == 5:
                    red = item.select_one('span[class="red"]') or item.select_one('b a font[color]')
                    if red:
                        t.upload_count = int(red.string)
                        t.red_seed = True
                    else:
                        t.upload_count = int(item.select_one('b a').string.replace(',', ''))

                elif i == 7:
                    t.download_count = int(
                        item.select_one('a b').string.replace(',', '') if item.select_one('a b') else 0)
            t.movies_release_year = mp.parse_year_by_str_list([t.name, t.subject])
            search_result.append(t)

        return search_result

    def parse_download_filename(self, response):
        if 'Content-Disposition' not in response.headers:
            print(response.headers)
            return None
        value, params = cgi.parse_header(unquote(response.headers['Content-Disposition']))
        return params['filename']
