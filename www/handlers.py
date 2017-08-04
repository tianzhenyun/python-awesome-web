#!/usr/bin/env python
# _*_ coding: utf-8 _*_

'''
Url Handlers
'''

import re, time, json, logging, hashlib, base64, asyncio
import markdown2

from apis import APIValueError, APIError, APIResourceNotFoundError, APIPermissionError, Page
from coreweb import  get, post

from models import User, Comment, Blog, next_id
from aiohttp import web
from config import configs

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')
COOKIE_NAME = 'awesome_session'
_COOKIE_KEY = configs.session.secret

'''
================== function ====================
'''
def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()


def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

def user2cookie(user, max_age):
    '''
    Generate cookie str by user
    :param user:
    :param max_age:
    :return:
    '''

    expires = str(int(time.time() + max_age))
    s = '{}-{}-{}-{}'.format(user.id, user.password, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


@asyncio.coroutine
def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid
    :param cookie_str:
    :return:
    '''

    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = yield from User.find(uid)
        if user is None:
            return None

        s = '{}-{}-{}-{}'.format(uid, user.password, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('cookie:{} is invalid, invalid sha1')
            return None
        user.password = '*' * 8
        return user
    except Exception as e:
        logging.exception(e)
        return None

def text2html(text):
    lines = map(lambda s: '<p>{}</p>'.format(s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

'''
====================== end function ====================
'''

'''
@get('/')
@asyncio.coroutine
def index(request):
    users = yield from User.find_all()
    return {
        '__template__': 'test.html',
        'users': users
    }
'''


'''
===================== client page =======================
'''
@get('/')
def index(*, page = '1'):
    '''
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test blog', summary = summary, created_at = time.time()-120),
        Blog(id='2', name='Javascript IT', summary = summary, created_at = time.time()-3600),
        Blog(id='3', name='Learn Swift', summary = summary, created_at = time.time()-7200),
    ]
    '''
    page_index = get_page_index(page)
    num = yield from Blog.find_number('count(id)')
    page = Page(num, page_index)
    if num == 0:
        blogs = []
    else:
        blogs = yield from Blog.find_all(order_by='created_at desc', limit=(page.offset, page.limit))

    return {
        '__template__': 'blogs.html',
        'page': page,
        'blogs': blogs
    }

@get('/blog/{id}')
def get_blog(id):
    blog = yield from Blog.find(id)
    if not blog:
        raise APIValueError('id', 'can not find blog id is :{}'.format(id))
    comments = yield from Comment.find_all('blog_id=?', [id], order_by='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }

@get('/test')
def test(request):
    return web.Response(body=b'<h1>Awesome Python3 Web</h1>', content_type='text/html')



@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }

@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('User signed out.')
    return r
'''
====================== end client page =====================
'''

'''
====================== manage page =========================
'''

@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }

@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/{}'.format(id)
    }

@get('/manage/blogs')
def manage_blogs(*, page = '1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }

@get('/manage/comments')
def manage_comment(*, page = '1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page)
    }

@get('/manage/users')
def manage_user(*, page = '1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page)
    }

'''
==================== end manage page =================
'''


'''
==================== backend api ====================
'''

@get('/api/users')
def api_get_users(request, *, page = '1'):
    '''get all users'''
    check_admin(request)
    page_index = get_page_index(page)
    num = yield from User.find_number('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page = p, users = ())
    users = yield from User.find_all(order_by='created_at desc', limit = (p.offset, p.limit))
    for u in users:
        u.password = '*' * 8
    return dict(page = p, users = users)

@get('/api/blogs/{id}')
def api_get_blog(*, id):
    blog = yield from Blog.find(id)
    return blog

@get('/api/blogs')
def api_blogs(*, page = '1'):
    page_index = get_page_index(page)
    num = yield from Blog.find_number('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page = p, blogs = ())
    blogs = yield from Blog.find_all(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)


@post('/api/users')
def api_register_user(*, email, name, password):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not password or not _RE_SHA1.match(password):
        raise APIValueError('password')

    users = yield from User.find_all('email=?', [email])
    if len(users) > 0:
        raise APIError('Register failed', 'email', 'Email is already in use.')

    uid = next_id()
    sha1_password = '{}:{}'.format(uid, password)
    logging.info('register password:{}, sha1_password:{}'.format(password, sha1_password))
    user = User(id=uid, name= name.strip(), email= email, password = hashlib.sha1(sha1_password.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/{}?d=mm&s=120'.format(hashlib.md5(email.encode('utf-8')).hexdigest()))
    yield from user.save()

    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '*' * 8
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@post('/api/authenticate')
def authenticate(*, email, password):
    if not email:
        raise APIValueError('email', 'Invalid Email')
    if not password:
        raise APIValueError('password', 'Invalid Password')
    users = yield from User.find_all('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist')

    user = users[0]

    #check password
    sha1_password = '{}:{}'.format(user.id, password)
    logging.info('login password:{}, sha1_password:{}'.format(password, sha1_password))
    if user.password != hashlib.sha1(sha1_password.encode('utf-8')).hexdigest():
        raise APIValueError('password', 'Invalid Password.')
    # authenticate ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '*' * 8
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@post('/api/blogs')
def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name can not be empty')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary can not be empty')
    if not content or not content.strip():
        raise APIValueError('content', 'content can not be empty')
    blog = Blog(user_id = request.__user__.id, user_name= request.__user__.name, user_image = request.__user__.image, name = name.strip(), summary = summary.strip(), content = content.strip())
    yield from blog.save()
    return blog

@post('/api/blogs/{id}/delete')
def api_delete_blog(request, *, id):
    logging.info('delete blog id: {}'.format(id))
    check_admin(request)
    blog = yield from Blog.find(id)
    if blog:
        yield from blog.remove()
        return blog
    raise APIValueError('id', 'id can not find...')
    
@post('/api/blogs/{id}')
def api_edit_blog(request, *, id, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name can not be empty')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary can not be empty')
    if not content or not content.strip():
        raise APIValueError('content', 'content can not be empty')
    #blog = Blog(user_id = request.__user__.id, user_name= request.__user__.name, user_image = request.__user__.image, name = name.strip(), summary = summary.strip(), content = content.strip())
    blog = yield from Blog.find(id)
    if not blog:
        raise APIValueError('id', 'request path error, id : {}'.format(id))
    blog.name = name
    blog.summary = summary
    blog.content = content
    yield from blog.update()
    return blog


@post('/api/blogs/{id}/comments')
def api_create_blog_comments(request, *, id, content):
    '''create blog comments'''
    if not request.__user__:
        raise APIPermissionError('please login first.')

    if not content or not content.strip():
        raise APIValueError('content', 'content can not be empty.')

    blog = yield from Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('blog', 'can not find blog, id :{}'.format(id))

    comment = Comment(blog_id = id, user_id= request.__user__.id, user_name = request.__user__.name, user_image = request.__user__.image, content = content.strip() )
    yield from comment.save()
    return comment

@get('/api/comments')
def api_comments(*, page = '1'):
    '''get all comments.'''
    page_index = get_page_index(page)
    num = yield from Comment.find_number('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page = p, comments = ())
    comments = yield from Comment.find_all(order_by = 'created_at desc', limit = (p.offset, p.limit))
    return dict(page = p, comments = comments)

@post('/api/comments/{comment_id}/delete')
def api_delete_comments(request, *, comment_id):
    '''delete comment.'''
    check_admin(request)
    comment = yield from Comment.find(comment_id)
    if comment is None:
        raise APIResourceNotFoundError('Comment', 'can not find comment, comment id: {}'.format(comment_id))
    yield from comment.remove()
    return comment


'''
==================== end backend api ====================
'''