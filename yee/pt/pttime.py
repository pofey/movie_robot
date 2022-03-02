# -!- coding: utf-8 -!-
import cgi
import copy
import re
import datetime
from urllib.parse import unquote
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging

from yee.pt.nexusprogramsite import NexusProgramSite
from yee.core.torrentmodels import Torrents, TorrentType, Torrent
from yee.pt.ptsiteparser import PTSiteParser
from yee.core.stringutils import StringUtils


class PTtime(NexusProgramSite):
    def get_site(self):
        """
        返回pt站的网址
        :return:
        """
        return 'https://www.pttime.org'

    def get_site_name(self):
        """
        这是pt网站的名称，确保唯一即可，集成到主程序时用作配置项
        :return:
        """
        return 'PTtime'

    def match_user(self, text):
        if text is None or text.strip() == '':
            return None
        # match_login_user = re.search(r'class=[\'"][^\'"]+[\'"]>(?:<a.+>)<b>(.+)</b>.*</a>.*</span>', text)
        match_login_user = re.findall(r'<a.+href="userdetails.php.+" class=\'User_Name\'><b>(.*?)</b></a>', text)[0]
        if match_login_user:
            # return StringUtils.trimhtml(match_login_user.group(1))
            return match_login_user
        else:
            return None


    def parse_torrents(self, text: str) -> Torrents:
        """
        通过返回的网页代码，解析列表页种子的所有信息
        :param text: 网页源代码
        :return:
        """
        soup = BeautifulSoup(text, features="lxml")
        search_result = []
        if not soup.find('table', class_='torrents'):
            return []
        for i, item in enumerate(soup.find('table', class_='mainouter mt5').find('table', class_='torrents').findAll('tr')[1:]):
            rowfollow_tag = item.findAll('td', 'rowfollow')
            if len(rowfollow_tag) != 0:
                t = Torrent()
                t.site_name = self.get_site_name()
                t.site = self.get_site()
                # 获取type/media_source
                find_imgs = rowfollow_tag[0].findAll('img')
                # t.media_source = find_imgs[1].get('title')
                # 获取类型
                t.primitive_type = find_imgs[0].get('alt')
                if t.primitive_type == 'Movies(电影)':
                    t.type = TorrentType.Movie
                    t.cate = TorrentType.Movie.value
                elif t.primitive_type in ['TV Series(电视剧)', 'TV Shows(综艺)']:
                    t.type = TorrentType.Series
                    t.cate = TorrentType.Series.value
                elif t.primitive_type == 'Music(音乐、专辑、演唱会)':
                    t.type = TorrentType.Music
                    t.cate = TorrentType.Music.value
                elif t.primitive_type == 'Documentaries(纪录片)':
                    t.type = TorrentType.Other
                    t.cate = '纪录片'
                elif t.primitive_type == 'ACGN(二次元)':
                    t.type = TorrentType.Other
                    t.cate = '动漫'
                elif t.primitive_type == 'Sex(骑兵/有码)':
                    t.type = TorrentType.AV
                    t.cate = TorrentType.AV.value
                elif t.primitive_type == 'AV(步兵/无码)':
                    t.type = TorrentType.AV
                    t.cate = TorrentType.AV.value
                else:
                    t.type = TorrentType.Other
                    t.cate = TorrentType.Other.value
                # 获取 id/name/url
                a_label = rowfollow_tag[1].find('a')
                t_id = a_label.get('href').split('&')[0][15:]
                t.id = int(t_id)
                t.name = a_label.get('title')
                t.url = self.get_site() + '/' + 'download.php?id=' + t_id
                # 获取object
                if rowfollow_tag[1].find('font', class_='promotion free'):
                    t_free_deadline = re.findall('<span title="([^"]+)"', str(rowfollow_tag[1]))
                    if len(t_free_deadline) == 0:
                        t.free_deadline = datetime.datetime.max
                    else:
                        t.free_deadline = datetime.datetime.strptime(t_free_deadline[0], '%Y-%m-%d %H:%M:%S')

                object_tag = copy.copy(rowfollow_tag[1])
                [s.extract() for s in rowfollow_tag[1].find_all("a")]
                [s.extract() for s in rowfollow_tag[1].find_all("b")]
                [s.extract() for s in rowfollow_tag[1].find_all("div")]
                [s.extract() for s in rowfollow_tag[1].find_all("img")]
                [s.extract() for s in rowfollow_tag[1].find_all("span")]
                subject = rowfollow_tag[1].text.replace('(剩余时间：)', '').strip()
                if subject == '':
                    subject = object_tag.find('b').text
                t.subject = subject
                # 获取种子发布时间
                t.publish_time = datetime.datetime.strptime(rowfollow_tag[4].find('span').get('title'), '%Y-%m-%d %H:%M:%S')
                # 获取文件大小
                t_file_size_re = re.findall('([1-9]\d*\.?\d*)(TiB|GiB|MiB|KiB|TB|GB|MB|KB)', rowfollow_tag[5].text)
                t.file_size = PTSiteParser.trans_unit_to_mb(float(t_file_size_re[0][0]), t_file_size_re[0][1])
                # 做种人数
                t.upload_count = int(rowfollow_tag[6].text.replace(',', ''))
                if rowfollow_tag[6].find('span') is not None or rowfollow_tag[6].find('font') is not None:
                    t.red_seed = True
                # 下载人数
                t.download_count = int(rowfollow_tag[7].text.replace(',', ''))
                search_result.append(t)
        return search_result

    def parse_download_filename(self, response):
        value, params = cgi.parse_header(response.headers['Content-Disposition'])
        filename = params['filename'].encode('ISO-8859-1').decode('utf8')
        return filename
