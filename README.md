# VirtKick WebVirtMgr Backend

This is a temporary, MVP backend for VirtKick.
VirtKick webapp is using it as a JSON API to libvirt.

The backend has been built on top of [WebVirtMgr](https://github.com/retspen/webvirtmgr),
a simple backend for KVM through libvirt.
It will soon be replaced with our own backend.

## Requirements

- Python 2.7
- Linux or Mac

## One time setup

```
sudo pip install -r requirements.txt
./manage.py syncdb
./manage.py collectstatic
```

## Development

```
./manage.py runserver
./console/webvirtmgr-novnc
xdg-open http://0.0.0.0:3000/ # open a browser
```

## Deployment

Since the authentication module is disabled, make sure the server listens on 127.0.0.1.

# License

WebVirtMgr Copyright (C) 2012-2014 Anatoliy Guskov and other contributors

VirtKick WebVirtMgr Backend Copyright (C) 2014 StratusHost Damian Nowak

The code is licensed under the [Apache Licence, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0.html).
