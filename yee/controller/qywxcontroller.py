import logging
import threading
import urllib
import xml.etree.ElementTree as ET

from flask import Blueprint, current_app, request

from yee.pt.torrentmodels import Torrents
from yee.service.movieservice import MovieService
from yee.service.notifyservice import NotifyService

qywx = Blueprint('qywx', __name__)

"""
企业微信搜索处理线程
"""


class QywxSearchThread(threading.Thread):
    def __init__(self, search_res_cache: dict, movie_service: MovieService, notify_service: NotifyService, keyword: str,
                 touser: str, server_url):
        threading.Thread.__init__(self)
        self.name = 'qywx-search'
        self.keyword = keyword
        self.movie_service = movie_service
        self.notify_service = notify_service
        self.touser = touser
        self.search_res_cache = search_res_cache
        self.server_url = server_url

    def run(self):
        try:
            """
            搜索后调用机器人的策略排序接口进行排序，控制返回给微信的搜索结果在5条
            取3条compress排序结果，2条compact排序结果
            """
            result: Torrents = self.movie_service.search_keyword(self.keyword)
            if result is None or len(result) == 0:
                self.notify_service.get_qywx().send_text(self.touser, f'{self.keyword} 搜索不到任何结果')
                return
            push_result: Torrents = []
            push_resids: set = set()
            if len(result) <= 5:
                push_result = result
            else:
                """
                取3条compress结果，2条compact结果
                """
                self.movie_service.sort_utils.sort(None, result, rule_name='compress')
                i = 0
                while i < 3:
                    t = result[i]
                    i += 1
                    if t.id in push_resids:
                        continue
                    push_result.append(t)
                    push_resids.add(t.id)
                self.movie_service.sort_utils.sort(None, result, rule_name='compact')
                i = 0
                while i < 2:
                    t = result[i]
                    i += 1
                    if t.id in push_resids:
                        continue
                    push_result.append(t)
                    push_resids.add(t.id)
            # 把推送的结果加内存缓存，保证点下载的时候能查到。缺陷是重启会丢结果。
            search_res_cache[self.keyword] = push_result
            for t in push_result:
                # 调用企业微信通知接口发送文本卡片通知
                self.notify_service.get_qywx().send_textcard(
                    self.touser, {
                        "title": f"{self.keyword} 来自{t.site_name}的搜索结果",
                        "description": f"<div>标题：{t.subject}</div><div>种子：{t.name}</div><div>尺寸：{round(t.file_size / 1024, 2)}GB</div><div>做种：{t.upload_count} 下完：{t.download_count}</div><div class=\"highlight\">点击立即开始下载</div>",
                        "url": f'{self.server_url}/api/qywx/download?tid={t.id}&keyword={urllib.parse.quote_plus(self.keyword)}',
                        "btntxt": "点击立即开始下载"
                    }
                )

        except Exception as e:
            logging.error('企业微信搜索失败：%s' % e, exc_info=True)


search_res_cache: dict = {}


@qywx.route('/download', methods=["GET"])
def download():
    tid = request.args.get('tid')
    keyword = request.args.get('keyword')
    if keyword not in search_res_cache:
        return '找不到搜索记录，请重新搜索%s后再点击下载' % keyword, 500
    res = search_res_cache[keyword]
    torrent = None
    for t in res:
        if t.id == tid:
            torrent = t
            break
    if torrent is None:
        return '找不到搜索记录，请重新搜索%s后再点击下载' % keyword, 500
    movie_service: MovieService = current_app.movie_service
    movie_service.free_download(torrent)
    return '下载任务已经提交：%s' % torrent.name


@qywx.route('/receive', methods=["GET", "POST"])
def receive():
    notify_service: NotifyService = current_app.notify_service
    wxcpt = notify_service.get_wxcpt()
    if wxcpt is None:
        logging.error('没有配置企业微信的接收消息设置，不能使用此功能。')
        return '', 500
    sign = request.args.get('msg_signature')
    ts = request.args.get('timestamp')
    nonce = request.args.get('nonce')
    if request.method == 'GET':
        """
        GET请求为应用设置接收API时的验证请求
        """
        verify_echo_str = request.args.get('echostr')
        ret, raw_echo_str = wxcpt.VerifyURL(sign, ts, nonce, verify_echo_str)
        if ret != 0:
            logging.error("ERR: VerifyURL ret: " + str(ret))
            return '', 401
        return raw_echo_str
    elif request.method == 'POST':
        post_data = request.data
        ret, rmsg = wxcpt.DecryptMsg(post_data, sign, ts, nonce)
        if ret != 0:
            logging.error("ERR: DecryptMsg ret: " + str(ret))
            return '', 401
        else:
            xml_tree = ET.fromstring(rmsg)
            content = xml_tree.find("Content").text
            touser = xml_tree.find('ToUserName').text
            fromuser = xml_tree.find('FromUserName').text
            # 直接回复一条消息，提示搜索中，这个回复必须5秒内完成，不能做太多操作，不然微信会处理超时
            res_msg = f"<xml><ToUserName>{touser}</ToUserName><FromUserName>{fromuser}</FromUserName><CreateTime>{xml_tree.find('CreateTime').text}</CreateTime><MsgType>{xml_tree.find('MsgType').text}</MsgType><Content>{content} 搜索中...</Content><MsgId>{xml_tree.find('MsgId').text}</MsgId><AgentID>{xml_tree.find('AgentID').text}</AgentID></xml>"
            ret, encrypt_msg = wxcpt.EncryptMsg(res_msg, nonce, ts)
            if ret != 0:
                logging.error("ERR: EncryptMsg ret: " + str(ret))
                return '', 401
            st = QywxSearchThread(search_res_cache, current_app.movie_service, notify_service, content, fromuser,
                                  current_app.server_url)
            st.start()
            return encrypt_msg, 200
