import random
from django import http
from django.views import View
from django_redis import get_redis_connection
import logging

from libs.captcha.captcha import captcha

logger = logging.getLogger('django')


class ImageCodeView(View):
    '''返回图形验证码的类视图'''

    def get(self, request, uuid):
        '''
        生成图形验证码, 保存到redis中, 另外返回图片
        :param request:请求对象
        :param uuid:浏览器端生成的唯一id
        :return:一个图片
        '''
        # 1.调用工具类 captcha 生成图形验证码
        # text, image = captcha.generate_captcha()
        text, image = captcha.generate_captcha()
        # 2.链接 redis, 获取链接对象
        print(text)
        redis_conn = get_redis_connection('verify_code')

        # 3.利用链接对象, 保存数据到 redis, 使用 setex 函数
        # redis_conn.setex('<key>', '<expire>', '<value>')
        redis_conn.setex('img_%s' % uuid, 300, text)

        return http.HttpResponse(image,
                                 content_type='image/jpg')


class SMSCodeView(View):

    def get(self, reqeust, mobile):
        redis_conn = get_redis_connection('verify_code')

        send_flag = redis_conn.get('send_flag_%s' % mobile)
        if send_flag:
            return http.JsonResponse({'code': 400,
                                      'errmsg': '发送短信过于频繁'})

        image_code_client = reqeust.GET.get('image_code')
        uuid = reqeust.GET.get('image_code_id')

        if not all([image_code_client, uuid]):
            return http.JsonResponse({'code': 400,
                                      'errmsg': '缺少必传参数'})

        image_code_server = redis_conn.get('img_%s' % uuid)
        if image_code_server is None:
            return http.JsonResponse({'code': 400,
                                      'errmsg': '图形验证码失效'})
        try:
            redis_conn.delete('img_%s' % uuid)
        except Exception as e:
            logger.error(e)

        image_code_server = image_code_server.decode()
        if image_code_client.lower() != image_code_server.lower():
            return http.JsonResponse({'code': 400,
                                      'errmsg': '输入图形验证码有误'})

        sms_code = '%06d' % random.randint(0, 999999)
        logger.info(sms_code)

        # 创建管道对象:
        pl = redis_conn.pipeline()

        # redis_conn.setex('sms_code_%s' % mobile, 300, sms_code)
        pl.setex('sms_code_%s' % mobile, 300, sms_code)

        # redis_conn.setex('send_flag_%s' % mobile, 60, 1)
        pl.setex('send_flag_%s' % mobile, 60, 1)

        # 执行管道:
        pl.execute()

        # CCP().send_template_sms(mobile, [sms_code, 5], 1)
        print(sms_code)
        return http.JsonResponse({'code': 0,
                                  'errmsg': '发送短信成功'})