import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

import apis

def get(path):
    """
    定义装饰器
    :param path: @get('path')
    :return:
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    """
    定义装饰器
    :param path: @post('path')
    :return:
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

# 收集没有默认值的命名关键字参数
# inspect作用是获取函数签名参数列表
def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if str(param.kind) == 'KEYWORD_ONLY':
            args.append(name)
        return tuple(args)

# 获取命名关键字参数
# 命名关键字参数举例：city='beijing', gender='male'
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if str(param.kind) == 'KEYWORD_ONLY':
            args.append(name)
    return tuple(args)

# 判断有无 命名关键字参数
def has_named_kw_arg(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if str(param.kind) == 'KEYWORD_ONLY':
            return True

# 判断有无 关键字参数
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if str(param.kind) == 'VAR_KEYWORD':
            return True

# 判断有无 是否含有名为'request'的参数，且为最后一个参数
def has_request_arg(fn):
    params = inspect.signature(fn).parameters
    sig = inspect.signature(fn)
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue # 找到request之后可以跳出循环
        if found and (str(param.kind) != 'VAR_POSITIONAL' and str(param.kind) != 'KEYWORD_ONLY' and str(
            param.kind != 'VAR_KEYWORD')):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

# 定义RequestHandler,正式向request参数获取URL处理函数所需的参数
class RequestHandler(object):

    # 接收app参数
    def __init__(self, app, fn):
        self._app = app
        self._fn = fn
        self._required_kw_args = get_required_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._has_named_kw_arg = has_named_kw_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_request_arg = has_request_arg(fn)

# __call__构造协程
    async def __call__(self, request):
        kw = None
        if self._has_named_kw_arg or self._has_var_kw_arg:

            # 判断request方法是否为POST
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest(text='Missing Content_Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(text="JSON body must be object")
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                     params = await request.post()
                     kw = dict(**params)
                else:
                    return web.HTTPBadRequest(text='Unsupported Content_Tpye:%s' % request.content_type)

            if request.method == 'GET':
                #The query string in the URL
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k,v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]

        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                    kw = copy
            for k,v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        if self._required_kw_args:
            for name in self._required_kw_args:
                if name not in kw:
                    return web.HTTPBadRequest(text='Missing argument:%s'%(name))

        logging.info("call with args:%s" % str(kw))

        try:
            r = await self._fn(**kw)
            return r
        # 要用APIError，作用是返回类似账户登录信息的错误
        except BaseException as e:
            return dict(error=e.error, data=e.data, message=e.message)

def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
        logging.info('add route %s %s => %s(%s)' % (
        method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
        app.router.add_route(method, path, RequestHandler(app, fn))

# 自动把handler模块的所有符合条件的函数注册了:
def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)


# 添加静态文件夹的路径
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.app_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/'), path)

