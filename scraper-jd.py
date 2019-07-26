import argparse
import os
import pickle
import random
import sys
import time
import json
import requests
import re
import logging
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

logging.basicConfig(
    format="[%(levelname)s] %(funcName)s: %(message)s",
    level=logging.INFO
)


class JDSpider:

    def __init__(self):
        # init url related
        self.home = 'https://passport.jd.com/new/login.aspx'
        self.login = 'https://passport.jd.com/uc/loginService'
        self.imag = 'https://authcode.jd.com/verify/image'
        self.auth = 'https://passport.jd.com/uc/showAuthCode'

        self.sess = requests.Session()

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36',
            'ContentType': 'text/html; charset=utf-8',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8',
            'Connection': 'keep-alive',
        }

        self.cookies = {

        }

        self.gname = ''    # 商品名称
        self.eid = 'DHPVSQRUFPP6GFJ7WPOFDKYQUGQSREWJLJ5QJPDOSJ2BYF55IZHP5XX3K2BKW36H5IU3S4R6GPU7X3YOGRJGW7XCF4'
        self.fp = 'b450f02af7d98727ef061e8806361c67'

    def checkLogin(self):
        # 恢复之前保存的cookie
        checkUrl = 'https://passport.jd.com/uc/qrCodeTicketValidation'
        try:
            print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++')
            print(f'{time.ctime()} > 自动登录中... ')
            with open('cookie', 'rb') as f:
                cookies = requests.utils.cookiejar_from_dict(pickle.load(f))
                response = requests.get(checkUrl, cookies=cookies)
                if response.status_code != requests.codes.OK:
                    print('登录过期, 请重新登录!')
                    return False
                else:
                    print('登录成功!')
                    self.cookies.update(dict(cookies))    # 从之前保存的cookie文件中恢复cookie
                    return True

        except Exception as e:
            logging.error(e)
            return False

    def login_by_QR(self):
        # jd login by QR code
        try:
            print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++')
            print(f'{time.ctime()} > 请打开京东手机客户端，准备扫码登录:')
            urls = (
                'https://passport.jd.com/new/login.aspx',
                'https://qr.m.jd.com/show',
                'https://qr.m.jd.com/check',
                'https://passport.jd.com/uc/qrCodeTicketValidation'
            )
            # step 1: open login page
            response = self.sess.get(
                urls[0],
                headers=self.headers
            )
            if response.status_code != requests.codes.OK:
                print(f"获取登录页失败:{response.status_code}")
                return False
            # update cookies
            self.cookies.update(response.cookies)

            # step 2: get QR image
            response = self.sess.get(
                urls[1],
                headers=self.headers,
                cookies=self.cookies,
                params={
                    'appid': 133,
                    'size': 147,
                    't': int(time.time() * 1000),
                }
            )
            if response.status_code != requests.codes.OK:
                print(f"获取二维码失败:{response.status_code}")
                return False

            # update cookies
            self.cookies.update(response.cookies)

            # save QR code
            image_file = 'qr.png'
            with open(image_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)

            # scan QR code with phone
            if os.name == "nt":
                # for windows
                os.system('start ' + image_file)
            else:
                if os.uname()[0] == "Linux":
                    # for linux platform
                    os.system("eog " + image_file)
                else:
                    # for Mac platform
                    os.system("open " + image_file)

            # step 3: check scan result    京东上也是不断去发送check请求来判断是否扫码成功
            self.headers['Host'] = 'qr.m.jd.com'
            self.headers['Referer'] = 'https://passport.jd.com/new/login.aspx'

            # check if QR code scanned
            qr_ticket = None
            retry_times = 100    # 尝试100次
            while retry_times:
                retry_times -= 1
                response = self.sess.get(
                    urls[2],
                    headers=self.headers,
                    cookies=self.cookies,
                    params={
                        'callback': 'jQuery%d' % random.randint(1000000, 9999999),
                        'appid': 133,
                        'token': self.cookies['wlfstk_smdl'],
                        '_': int(time.time() * 1000)
                    }
                )
                if response.status_code != requests.codes.OK:
                    continue
                rs = json.loads(re.search(r'{.*?}', response.text, re.S).group())
                if rs['code'] == 200:
                    print(f"{rs['code']} : {rs['ticket']}")
                    qr_ticket = rs['ticket']
                    break
                else:
                    print(f"{rs['code']} : {rs['msg']}")
                    time.sleep(3)

            if not qr_ticket:
                print("二维码登录失败")
                return False

            # step 4: validate scan result
            # must have
            self.headers['Host'] = 'passport.jd.com'
            self.headers['Referer'] = 'https://passport.jd.com/new/login.aspx'
            response = requests.get(
                urls[3],
                headers=self.headers,
                cookies=self.cookies,
                params={'t': qr_ticket},
            )
            if response.status_code != requests.codes.OK:
                print(f"二维码登录校验失败:{response.status_code}")
                return False

            # 京东有时候会认为当前登录有危险，需要手动验证
            # url: https://safe.jd.com/dangerousVerify/index.action?username=...
            res = json.loads(response.text)
            if not response.headers.get('p3p'):
                if 'url' in res:
                    print(f"需要手动安全验证: {res['url']}")
                    return False
                else:
                    print(res)
                    print('登录失败!!')
                    return False

            # login succeed
            self.headers['P3P'] = response.headers.get('P3P')
            self.cookies.update(response.cookies)

            # 保存cookie
            with open('cookie', 'wb') as f:
                pickle.dump(self.cookies, f)

            print("登录成功")
            return True

        except Exception as e:
            print(e)
            raise

    def good_stock(self, skuId, area_id):
        """
        监控库存
        :return:
        """
        url = "https://c0.3.cn/stocks"

        params = {
            "skuIds": skuId,
            "area": area_id,    # 收货地址id
            "type": "getstocks",
            "_": int(time.time()*1000)
        }

        headers = {"Referer": "https://item.jd.com/5504364.html",
                   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36",
                   }
        try:
            response = requests.get(url, params=params, headers=headers)
            response.encoding = 'utf-8'
            # print(response.text)
            json_dict = json.loads(response.text)
            stock_state = json_dict[skuId]['StockState']    # 33: 现货    34: 无货     40: 可配货
            stock_state_name = json_dict[skuId]['StockStateName']    # 这个乱码
            return stock_state, stock_state_name
        except Exception as e:
            logging.error(e)

        return 0, ''

    def good_detail(self, skuId, area_id):
        # return good detail
        good_data = {
            'id': skuId,
            'name': '',
            'cart_link': '',
            'price': '',
            'stock': '',
            'stockName': '',
        }
        try:
            # 商品详情页
            detail_link = f"https://item.jd.com/{skuId}.html"
            response = requests.get(detail_link)
            soup = BeautifulSoup(response.text, "lxml")
            # 产品名称
            name = soup.find('div', class_="sku-name").text.strip()
            good_data['name'] = name
            # 购物车链接
            cart_link = soup.find("a", id="InitCartUrl")['href']
            if cart_link[:2] == '//':  # '//cart.jd.com/gate.action?pid=5504364&pcount=1&ptype=1'
                cart_link = 'http:' + cart_link
            good_data['cart_link'] = cart_link

        except Exception as e:
            logging.error(e)

        good_data['price'] = self.good_price(skuId)
        good_data['stock'], good_data['stockName'] = self.good_stock(skuId, area_id)
        print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        print(f'{time.ctime()} > 商品详情')
        print(f"编号：{good_data['id']}")
        print(f"库存：{good_data['stockName']}")
        print(f"价格：{good_data['price']}")
        print(f"名称：{good_data['name']}")
        print(f"加入购物车链接：{good_data['cart_link']}")
        return good_data

    def good_price(self, skuId):
        # get good price
        url = 'http://p.3.cn/prices/mgets'
        payload = {
            'type': 1,
            'skuIds': 'J_' + skuId,
        }
        price = '?'
        try:
            response = requests.get(url, params=payload)
            resp_txt = response.text.strip()
            json_dict = json.loads(resp_txt[1:-1])  # 去掉首尾的[]
            price = json_dict['p']
        except Exception as e:
            logging.error(e)
        return price

    def buy(self, options):
        # good detail
        good_data = self.good_detail(options.good, options.area)
        if good_data['stock'] != 33:    # 如果没有现货
            # flush stock state
            while good_data['stock'] != 33 and options.flush:
                print(good_data['stock'], good_data['name'])
                time.sleep(options.wait / 1000.0)
                good_data['stock'], good_data['stockName'] = self.good_stock(skuId=options.good,
                                                                             area_id=options.area)

        cart_link = good_data['cart_link']
        if cart_link == '':    # 如果有货, 但是没有购物车链接
            print("没有购物车链接")
            return False

        try:
            # change buy count
            if options.count != 1:
                cart_link = cart_link.replace('pcount=1', 'pcount={0}'.format(options.count))

            response = self.sess.get(cart_link, cookies=self.cookies)
            soup = BeautifulSoup(response.text, "lxml")
            tag = soup.find("h3", class_='ftx-02')
            if tag:
                print(tag.text)
            else:
                print('添加到购物车失败')
                return False

        except Exception as e:
            logging.error(e)
            return False
        else:
            self.cart_detail()
            return self.order_info(options.submit)

    def cart_detail(self):
        # list all goods detail in cart
        cart_url = 'https://cart.jd.com/cart.action'
        cart_header = '购买    数量     价格        总价        商品'
        cart_format = '{0:8}{1:8}{2:12}{3:12}{4}'

        # try:
        response = self.sess.get(cart_url, cookies=self.cookies)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "lxml")
        print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        print(f'{time.ctime()} > 购物车明细')
        print(cart_header)

        try:
            for item in soup.select('div.item-form'):
                check = item.select('div.cart-checkbox input')[0]['checked']
                check = ' + ' if check else ' - '
                count = item.select('div.quantity-form input')[0]['value']
                price = item.select('div.p-price strong')[0].text.strip()
                sums = item.select('div.p-sum strong')[0].text.strip()
                gname = item.select('div.p-name a')[0].text.strip()
                #: ￥字符解析出错, 输出忽略￥
                print(cart_format.format(check, count, price, sums, gname))
                self.gname = gname    #

            t_count = soup.select('div.amount-sum em')[0].text
            t_value = soup.select('span.sumPrice em')[0].text
            print(f'总数: {t_count}')
            print(f'总额: {t_value[1:]}')
        except Exception as e:
            logging.error(e)

    def order_info(self, submit=False):
        """
        下单
        :param submit:
        :return: 是否下单成功
        """
        # get order info detail, and submit order
        print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        print(f'{time.ctime()} > 订单详情')

        try:
            order_url = 'http://trade.jd.com/shopping/order/getOrderInfo.action'
            payload = {
                'rid': str(int(time.time() * 1000)),
            }

            # 获取预下单页面
            rs = self.sess.get(order_url, params=payload, cookies=self.cookies)
            soup = BeautifulSoup(rs.text, "html.parser")

            # order summary
            payment = soup.find(id='sumPayPriceId').text
            detail = soup.find(class_='fc-consignee-info')

            if detail:
                snd_usr = detail.find(id='sendMobile').text    # 收货人
                snd_add = detail.find(id='sendAddr').text      # 收货地址

                print(f'应付款：{payment}')
                print(snd_usr)
                print(snd_add)

            # just test, not real order
            if not submit:
                return False

            # order info
            sopNotPutInvoice = soup.find(id='sopNotPutInvoice')['value']

            btSupport = get_btSupport(soup)
            ignorePriceChange = soup.find(id='ignorePriceChange')['value']
            riskControl = soup.find(id='riskControl')['value']

            data = {
                'overseaPurchaseCookies': '',
                'vendorRemarks': [],    # 貌似是订单备注    [{"venderId":"632952","remark":""}]
                'submitOrderParam.sopNotPutInvoice': sopNotPutInvoice,    # 货票分离开关值  false or true
                'submitOrderParam.trackID': 'TestTrackId',    # 写死
                'submitOrderParam.get_ignorePriceChange': ignorePriceChange,    # 写死
                'submitOrderParam.btSupport': btSupport,    # 是否支持白条
                'submitOrderParam.eid': self.eid,    # 设备id equipment id
                'submitOrderParam.fp': self.fp,      # 貌似也和设备信息有关
                'riskControl': riskControl,
                'submitOrderParam.jxj': '1',     # 惊喜金 我也不知道是个啥玩意
                'submitOrderParam.trackId': 'cc46bf84f6274988c7cde62fce0cc11a',
            }
            # print(data)
            order_url = 'http://trade.jd.com/shopping/order/submitOrder.action'
            rp = self.sess.post(order_url, data=data, cookies=self.cookies, headers={
                'Referer': 'https://trade.jd.com/shopping/order/getOrderInfo.action?rid='+payload['rid'],
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36',
            })
            # print(rp.text)

            if rp.status_code == 200:
                js = json.loads(rp.text)
                if js['success']:
                    print(f"下单成功！订单号：{js['orderId']}")
                    print('请前往京东官方商城付款')
                    # 发送邮件提醒功能请自己添加相应的邮箱账号和密码
                    # send_email('下单成功', f'商品名称: {self.gname}, 应付款：{payment}, 请前往京东官方商城付款')
                    return True
                else:
                    # 这个else分支还未测试过是否能用
                    print('下单失败！<{0}: {1}>'.format(js['resultCode'], js['message']))
                    if js['resultCode'] == '60017':
                        # 60017: 您多次提交过快，请稍后再试
                        time.sleep(1)
            else:
                print('请求失败. StatusCode:', rp.status_code)

        except Exception as e:
            logging.error(e)

        return False


def get_btSupport(soup):
    """
    是否支持白条
    :param soup:
    :return:
    """
    if len(soup.find_all(class_='payment-item', attrs={'onlinepaytype': '1'})) == 0:
        if "payment-item-disabled" in str(soup.find_all(class_='payment-item', attrs={'onlinepaytype': '1'})):
            return '0'
    else:
        return '1'


def send_email(subject, message):
    try:
        my_sender = ''  # 邮件发送者
        my_pass = ''  # 邮件发送者邮箱密码
        my_user = ''     # 收件人邮箱
        msg = MIMEText(message, 'html', 'utf-8')
        msg['From'] = formataddr(["来自京东自动下单机器人", my_sender])
        msg['To'] = formataddr(["由我的网易邮箱接收", my_user])
        msg['Subject'] = subject

        server = smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(my_sender, my_pass)
        server.sendmail(my_sender, [my_user, ], msg.as_string())
        server.quit()
    except Exception as e:
        logging.error(e)


if __name__ == '__main__':

    # help message
    parser = argparse.ArgumentParser(description='Simulate to login Jing Dong, and buy sepecified good')
    parser.add_argument('-a', '--area',
                        help='Area string, like: 1_72_2799_0 for Beijing', default='')
    parser.add_argument('-g', '--good',
                        help='Jing Dong good ID', default='')
    parser.add_argument('-c', '--count', type=int,
                        help='The count to buy', default=1)
    parser.add_argument('-w', '--wait',
                        type=int, default=1000,
                        help='Flush time interval, unit MS')
    parser.add_argument('-f', '--flush',
                        action='store_true',
                        help='Continue flash if good out of stock',
                        default=True)
    parser.add_argument('-s', '--submit',
                        action='store_true',
                        help='Submit the order to Jing Dong',
                        default=True)
    iPad_Pro_id = '5173441'    # iPad Pro 10.5的sku    https://item.jd.com/5504364.html
    # 浙江省台州市温岭市松门镇的id, 如何获取area_id请看area_id.png
    area_id = '15_1290_22049_22142'
    options = parser.parse_args()

    if options.good == '':
        options.good = iPad_Pro_id
    if options.area == '':
        options.area = area_id

    spider = JDSpider()
    if not spider.checkLogin():
        if not spider.login_by_QR():
            sys.exit(-1)

    while not spider.buy(options) and options.flush:
        time.sleep(options.wait / 1000.0)
