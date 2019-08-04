"""

import inspect

def a(a, b=0, *c, z, e=1, **f):
    pass

aa = inspect.signature(a).parameters
print("inspect.signature(fn)是:%s" % aa)
print("inspect.signature(fn)的类型：%s" % (type(aa)))
print("\n")

list1 = ['a', 'b', 'c', 'd']
list2 = ['apple', 'boy', 'cat', 'dog']
for x, y in aa.items():
    print(x, 'is', y)

"""
# 关键字参数，**kw类型其实是dict字典
def person1(name, age, **kw):
    print('name:', name, 'age:', age, 'other:', kw)

person1('Michael', 30)

# 如果要限制关键字参数的名字，就可以用命名关键字参数，例如，只接收city和job作为关键字参数。这种方式定义的函数如下：
def person2(name, age, *, city, job):
    print(name, age, city, job)

person2('Jack', 24, 'Engineer', 'Beijing' )