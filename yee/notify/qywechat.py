import datetime
import json
import logging

from yee.core.httputils import RequestUtils
from yee.core.stringutils import StringUtils
from yee.notify.notify import Notify

"""
企业微信通知
"""


class QywechatNotify(Notify):
    req = RequestUtils(request_interval_mode=False)

    def __init__(self, **args):
        args.setdefault('touser', '@all')
        self.args = args
        self.message_template = args.get('message_template')
        self.token_cache = None
        self.token_expires_time = None

    def get_access_token(self):
        if self.token_expires_time is not None and self.token_expires_time >= datetime.datetime.now():
            return self.token_cache
        res = self.req.get(
            'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=%s&corpsecret=%s' % (
                self.args["corpid"], self.args["corpsecret"]))
        json = res.json()
        if json['errcode'] == 0:
            self.token_expires_time = datetime.datetime.now() + datetime.timedelta(seconds=json['expires_in'] - 500)
            self.token_cache = json['access_token']
            return self.token_cache
        else:
            return None

    def get_touser(self, context: dict):
        context.setdefault('nickname', None)
        touser = '@all'
        if 'touser' in self.args.keys():
            touser = self.args['touser']
        users = self.args.get('users')
        if users is not None and len(users) > 0:
            for user in users:
                if user.get('touser') is not None and user.get('nickname') == context['nickname']:
                    touser = user.get('touser')
        return touser

    def send(self, message_template: str, context: dict):
        access_token = self.get_access_token()
        if access_token is None:
            logging.error('获取企业微信access_token失败，请检查你的corpid和corpsecret配置')
            return
        if message_template not in self.message_template:
            logging.error('找不到通知消息模版：%s' % (message_template))
            return
        mt = self.message_template[message_template]
        title = mt['title']
        message_pattern = mt['message']
        url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=' + access_token
        res = self.req.post_res(url, params=json.dumps({
            'touser': self.get_touser(context),
            'agentid': self.args['agentid'],
            'msgtype': 'news',
            'news': {
                "articles": [
                    {
                        "title": StringUtils.replace_var(title, context),
                        "description": StringUtils.replace_var(message_pattern, context),
                        "url": context['url'],
                        "picurl": context['cover']
                    }
                ]
            }
        }))
        if res.json()['errcode'] != 0:
            logging.error('企业微信推送失败：%s' % res.json())

    def send_textcard(self, touser: str, textcard: dict):
        access_token = self.get_access_token()
        if access_token is None:
            logging.error('获取企业微信access_token失败，请检查你的corpid和corpsecret配置')
            return
        url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=' + access_token
        jsonstr = json.dumps({
            'touser': touser,
            'agentid': self.args['agentid'],
            'msgtype': 'textcard',
            'textcard': textcard
        })
        res = self.req.post_res(url, params=jsonstr)
        if res.json()['errcode'] != 0:
            logging.error('企业微信推送失败：%s' % res.json())

    def send_text(self, touser: str, content: str):
        access_token = self.get_access_token()
        if access_token is None:
            logging.error('获取企业微信access_token失败，请检查你的corpid和corpsecret配置')
            return
        url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=' + access_token
        res = self.req.post_res(url, params=json.dumps({
            'touser': touser,
            'agentid': self.args['agentid'],
            'msgtype': 'text',
            'text': {
                "content": content
            }
        }))
        if res.json()['errcode'] != 0:
            logging.error('企业微信推送失败：%s' % res.json())
