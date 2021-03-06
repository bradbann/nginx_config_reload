#!/usr/bin/python
# -*- coding: utf-8 -*-
__author__ = 'web'

from copy import deepcopy
from grammar_parser import parser


def _parse_server_line(line):
    """ server的配置本文 解析成对象
        :param "server ip:port max_fails=3 fail_timeout=15s;"
        :return ["ip:port", "3", "15s"]
    """
    server = []
    part = line.split()
    if len(part) > 2:
        server.append(part[1])
        for p in part[2:-1]:
            middle = p.split('=')[1]
            server.append(middle)
        # 除去最后一个元素的;
        last = part[-1][:-1].split('=')[1]
        server.append(last)
    else:
        # 格式: server ip:port;
        server.append(part[1][:-1])  # 除去结尾的;
        server.append('1')  # 加入 max_fails 默认值
        server.append('10s')  # 加入fail_timeout 默认值
    return server


def server_to_line(server):
    """ 根据 server 对象生成文本 """
    return "    server %s max_fails=%s fail_timeout=%s;\n" \
           % (server[0], server[1], server[2])


class NotFindUpstream(Exception):
    pass


class NotFindServer(NotFindUpstream):
    pass

class ServerExsit(NotFindUpstream):
    pass


class UpstreamGroup(object):
    """
    upstreams = {
                    us_name: [ 'lb',
                               [server, max_fails, fail_timeout],
                               [...],...
                             ],
                    us_name2: [....]
                }
    """

    def __init__(self, ngx_conf):
        self.ngx_conf = ngx_conf
        self.group = self.get_upstream_group()

    def get_upstream_conf(self):
        """ 取出关于 upstream 的配置文本 """
        find_upstream = False
        res = []
        with open(self.ngx_conf) as ngx:
            line = ngx.readline()
            while line:
                if line[0] != '#' and 'upstream' in line and '{' in line:
                    find_upstream = True
                    res.append(line)
                elif find_upstream and '}' not in line:
                    res.append(line)
                elif find_upstream and '}' in line:
                    find_upstream = False
                    res.append(line)
                line = ngx.readline()
        return ''.join(res)

    def get_upstream_group(self):
        """返回upstreams对象"""
        # parser = new_parser()
        return parser.parse(self.get_upstream_conf())

    def get_upstream(self, us_name):
        """返回指定 upstream_name 的us对象"""
        us_name = str(us_name)
        try:
            # 对象的副本传递到 Upstream
            us_obj = deepcopy(self.get_upstream_group()[us_name])
            us = Upstream(us_name, us_obj)
            return us
        except KeyError, e:
            raise NotFindUpstream("Upstream %s is not in conf" % e)

    def update_upstream_group(self, us):
        """更新或添加 upstream 对象"""
        if isinstance(us, Upstream):
            us_obj = [us.lb_algorithm]
            for server in us.servers:
                us_obj.append(server)
            self.group[us.us_name] = us_obj
            return self.group[us.us_name]

    def del_upstream(self, *args):
        """删除一个或多个指定的 us对象,返回删除后的 upstreams 对象"""
        try:
            for us_name in args:
                self.group.pop(us_name)
            return self.group
        except NotFindUpstream, e:
            return self.group

    def dump_upstreams(self):
        """upstreams对象转为文本"""
        res = []
        for us_name, us_stmt in self.group.items():
            res.append("upstream %s {\n" % us_name)
            if us_stmt[0] != 'default':
                res.append('    ' + us_stmt[0] + ';\n')
            us_stmt.pop(0)
            for server in us_stmt:
                res.append(server_to_line(server))
            res.append('}\n')
        return ''.join(res)

    def update_ngx_conf(self):
        data = self.dump_upstreams()
        if data:
            with open(self.ngx_conf, 'w') as f:
                f.write(data)

class Upstream(object):
    def __init__(self, us_name, us_obj):
        # us_obj = ['lb',[server],[server],...]
        self.us_name = us_name
        self.lb_algorithm = us_obj[0]
        us_obj.pop(0)
        self.servers = us_obj

    def add_server(self, ip, port, max_fails=None, fail_timeout=None):
        """ 添加server对象"""
        for server in self.servers:
            if ip in server[0]:
                raise ServerExsit("%s already in upstream %s" % (ip, self.us_name))
        if not max_fails:
            max_fails = "1"
        if not fail_timeout:
            fail_timeout = "10s"
        self.servers.append([
            ip + ':' + port,
            max_fails,
            fail_timeout
        ])

    def del_server(self, ip):
        """ 根据 ip 删除 server 对象 """
        for index, server in enumerate(self.servers):
            if ip in server[0]:
                self.servers.pop(index)
                return self.servers
        raise NotFindServer("%s is not in upstream %s" % (ip, self.us_name))


if __name__ == '__main__':
    usgrp = UpstreamGroup("../test/conf/nginx.conf")
    fuck = usgrp.get_upstream('fuck')
    fuck.add_server('111.111.111.1', '888' '1', '15s')
    usgrp.update_upstream_group(fuck)
    print(usgrp.dump_upstreams())
