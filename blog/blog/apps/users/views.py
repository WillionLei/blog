import json
import re

from django import http
from django.contrib.auth import login
from django.db import DatabaseError
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from django.views import View
from django_redis import get_redis_connection

from users.models import Users


class UsernameCountView(View):
    """判断用户名是否重复注册"""

    def get(self, request, username):
        """
        :param request: 请求对象
        :param username: 用户名
        :return: JSON
        """
        # 获取数据库中该用户名对应的个数
        count = Users.objects.filter(username=username).count()

        return http.JsonResponse({'code': 0,
                                  'errmsg': 'OK',
                                  'count': count})


class MobileCountView(View):

    def get(self, request, mobile):
        '''
        判断电话是否重复, 返回对应的个数
        :param request:
        :param mobile:
        :return:
        '''
        # 1.从数据库中查询 mobile 对应的个数
        count = Users.objects.filter(mobile=mobile).count()

        # 2.拼接参数, 返回
        return http.JsonResponse({'code':0,
                                  'errmsg':'ok',
                                  'count':count})


class RegisterView(View):

    def post(self, request):
        # 1.接收参数(json类型的参数)
        dict = json.loads(request.body.decode())
        username = dict.get('username')
        password = dict.get('password')
        password2 = dict.get('password2')
        mobile = dict.get('mobile')
        allow = dict.get('allow')
        sms_code_client = dict.get('sms_code')

        # 2.校验参数(总体 + 单个)
        # 2.1总体检验,查看是否有为空的参数:
        if not all([username, password, password2, mobile, sms_code_client]):
            return http.HttpResponseForbidden('缺少必传参数')

        # 单个检验,查看是否能够正确匹配正则
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return http.HttpResponseForbidden('用户名为5-20位的字符串')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.HttpResponseForbidden('密码为8-20位的字符串')

        if password != password2:
            return http.HttpResponseForbidden('密码不一致')

        if not re.match(r'^1[345789]\d{9}$', mobile):
            return http.HttpResponseForbidden('手机号格式不正确')

        if allow != 'true':
            return http.HttpResponseForbidden('请勾选用户同意')

        # 链接 redis, 获取链接对象
        redis_conn = get_redis_connection('verify_code')

        # 从 redis 取保存的短信验证码
        sms_code_server = redis_conn.get('sms_code_%s' % mobile)
        if sms_code_server is None:
            return http.HttpResponse(status=400)

        # 对比
        if sms_code_client != sms_code_server.decode():
            return http.HttpResponse(status=400)

        # 3.往 mysql 保存数据
        # 对数据库进行操作, 需要 try... except...
        try:
            user = Users.objects.create_user(username=username,
                                            password=password,
                                            mobile=mobile)
        except DatabaseError:
            # 如果出错, 返回400
            return http.HttpResponse(status=400)
        login(request, user)
        response = HttpResponse()

        response.set_cookie('username', user.username, max_age=3600 * 24 * 14)

        # 7.返回
        return response