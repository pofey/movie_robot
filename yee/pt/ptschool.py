# -!- coding: utf-8 -!-
import cgi
import copy
import re
import datetime
from urllib.parse import unquote
from bs4 import BeautifulSoup

from yee.pt.nexusprogramsite import NexusProgramSite
from yee.core.torrentmodels import Torrents, TorrentType, Torrent
from yee.pt.ptsiteparser import PTSiteParser


class PTSchoolV2(NexusProgramSite):
    def get_site(self):
        """
        返回pt站的网址
        :return:
        """
        return 'https://pt.btschool.club'

    def get_site_name(self):
        """
        这是pt网站的名称，确保唯一即可，集成到主程序时用作配置项
        :return:
        """
        return 'ptschool'

    def parse_torrents(self, text: str) -> Torrents:
        """
        通过返回的网页代码，解析列表页种子的所有信息
        :param text: 网页源代码
        :return:
        """
        search_result = []
        soup = BeautifulSoup(text)
        try:
            find_tr = soup.find('table', class_='mainouter').find('table', class_='torrents').findAll('tr')[1:]
        except Exception as e:
            find_tr = []
        for i, item in enumerate(find_tr):
            rowfollow_tag = item.findAll('td', 'rowfollow')
            if len(rowfollow_tag) != 0:
                t = Torrent()
                t.site_name = self.get_site_name()
                t.site = self.get_site()
                # 获取type/media_source
                find_imgs = rowfollow_tag[0].findAll('img')
                t.media_source = find_imgs[1].get('title')
                # 获取类型
                t.primitive_type = find_imgs[0].get('alt')
                if t.primitive_type == '电影/Movies':
                    t.type = TorrentType.Movie
                    t.cate = TorrentType.Movie.value
                elif t.primitive_type in ['连续剧/TV-Series', '综艺/TV-Show']:
                    t.type = TorrentType.Series
                    t.cate = TorrentType.Series.value
                elif t.primitive_type == '音乐/Music':
                    t.type = TorrentType.Music
                    t.cate = TorrentType.Music.value
                elif t.primitive_type == '纪录片/Documentary':
                    t.type = TorrentType.Other
                    t.cate = '纪录片'
                elif t.primitive_type == '动漫/Animation':
                    t.type = TorrentType.Other
                    t.cate = '动漫'
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
                for free_item in rowfollow_tag[1].findAll('img'):
                    if "alt" in free_item.attrs and "Free" in free_item.get('alt'):
                        t_free_deadline = re.findall('剩余时间：<span title="([^"]+)"', str(rowfollow_tag[1]))
                        if len(t_free_deadline) == 0:
                            t.free_deadline = datetime.datetime.max
                        else:
                            t.free_deadline = datetime.datetime.strptime(t_free_deadline[0], '%Y-%m-%d %H:%M:%S')
                        break
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
                t.publish_time = datetime.datetime.strptime(rowfollow_tag[3].find('span').get('title'), '%Y-%m-%d %H:%M:%S')
                # 获取文件大小
                t_file_size_re = re.findall('([1-9]\d*\.?\d*)(TiB|GiB|MiB|KiB|TB|GB|MB|KB)', rowfollow_tag[4].text)
                t.file_size = PTSiteParser.trans_unit_to_mb(float(t_file_size_re[0][0]), t_file_size_re[0][1])
                # 做种人数
                t.upload_count = int(rowfollow_tag[5].text.replace(',', ''))
                if rowfollow_tag[5].find('span') is not None or rowfollow_tag[5].find('font') is not None:
                    t.red_seed = True
                # 下载人数
                t.download_count = int(rowfollow_tag[6].text.replace(',', ''))
                search_result.append(t)
        return search_result

    def parse_download_filename(self, response):
        if 'Content-Disposition' not in response.headers:
            print(response.headers)
            return None
        value, params = cgi.parse_header(unquote(response.headers['Content-Disposition']))
        return params['filename']

