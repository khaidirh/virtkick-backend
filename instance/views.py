from string import letters, digits
from random import choice

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponse
from django.template import RequestContext
from django.utils.translation import ugettext_lazy as _
import json

from instance.models import Instance
from servers.models import Compute

from vrtManager.instance import wvmInstances, wvmInstance

from libvirt import libvirtError, VIR_DOMAIN_XML_SECURE
from webvirtmgr.settings import TIME_JS_REFRESH, QEMU_KEYMAPS

from shared.helpers import render


from Queue import Queue
from threading import Thread

class Worker(Thread):
    """Thread executing tasks from a given tasks queue"""
    def __init__(self, tasks):
        Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.start()

    def run(self):
        while True:
            func, args, kargs = self.tasks.get()
            try: func(*args, **kargs)
            except Exception, e: print e
            self.tasks.task_done()

class ThreadPool:
    """Pool of threads consuming tasks from a queue"""
    def __init__(self, num_threads):
        self.tasks = Queue(num_threads)
        for _ in range(num_threads): Worker(self.tasks)

    def add_task(self, func, *args, **kargs):
        """Add a task to the queue"""
        self.tasks.put((func, args, kargs))

    def wait_completion(self):
        """Wait for completion of all the tasks in the queue"""
        self.tasks.join()

def instusage(request, host_id, vname):
    """
    Return instance usage
    """
    cookies = {}
    datasets = {}
    datasets_rd = []
    datasets_wr = []
    json_blk = []
    cookie_blk = {}
    blk_error = False
    datasets_rx = []
    datasets_tx = []
    json_net = []
    cookie_net = {}
    net_error = False
    networks = None
    disks = None

    compute = Compute.objects.get(id=host_id)

    try:
        conn = wvmInstance(compute.hostname,
                           compute.login,
                           compute.password,
                           compute.type,
                           vname)
        status = conn.get_status()
        if status == 3 or status == 5:
            networks = conn.get_net_device()
            disks = conn.get_disk_device()
    except libvirtError:
        status = None

    if status and status == 1:
        try:
            blk_usage = conn.disk_usage()
            cpu_usage = conn.cpu_usage()
            net_usage = conn.net_usage()
            conn.close()
        except libvirtError:
            blk_usage = None
            cpu_usage = None
            net_usage = None

        try:
            cookies['cpu'] = request._cookies['cpu']
        except KeyError:
            cookies['cpu'] = None

        try:
            cookies['hdd'] = request._cookies['hdd']
        except KeyError:
            cookies['hdd'] = None

        try:
            cookies['net'] = request._cookies['net']
        except KeyError:
            cookies['net'] = None

        if cookies['cpu'] == '{}' or not cookies['cpu'] or not cpu_usage:
            datasets['cpu'] = [0]
        else:
            datasets['cpu'] = eval(cookies['cpu'])
        if len(datasets['cpu']) > 10:
            while datasets['cpu']:
                del datasets['cpu'][0]
                if len(datasets['cpu']) == 10:
                    break
        if len(datasets['cpu']) <= 9:
            datasets['cpu'].append(int(cpu_usage['cpu']))
        if len(datasets['cpu']) == 10:
            datasets['cpu'].append(int(cpu_usage['cpu']))
            del datasets['cpu'][0]

        cpu = {
            'labels': [""] * 10,
            'datasets': [
                {
                    "fillColor": "rgba(241,72,70,0.5)",
                    "strokeColor": "rgba(241,72,70,1)",
                    "pointColor": "rgba(241,72,70,1)",
                    "pointStrokeColor": "#fff",
                    "data": datasets['cpu']
                }
            ]
        }

        for blk in blk_usage:
            if cookies['hdd'] == '{}' or not cookies['hdd'] or not blk_usage:
                datasets_wr.append(0)
                datasets_rd.append(0)
            else:
                datasets['hdd'] = eval(cookies['hdd'])
                try:
                    datasets_rd = datasets['hdd'][blk['dev']][0]
                    datasets_wr = datasets['hdd'][blk['dev']][1]
                except:
                    blk_error = True

            if not blk_error:
                if len(datasets_rd) > 10:
                    while datasets_rd:
                        del datasets_rd[0]
                        if len(datasets_rd) == 10:
                            break
                if len(datasets_wr) > 10:
                    while datasets_wr:
                        del datasets_wr[0]
                        if len(datasets_wr) == 10:
                            break

                if len(datasets_rd) <= 9:
                    datasets_rd.append(int(blk['rd']) / 1048576)
                if len(datasets_rd) == 10:
                    datasets_rd.append(int(blk['rd']) / 1048576)
                    del datasets_rd[0]

                if len(datasets_wr) <= 9:
                    datasets_wr.append(int(blk['wr']) / 1048576)
                if len(datasets_wr) == 10:
                    datasets_wr.append(int(blk['wr']) / 1048576)
                    del datasets_wr[0]

                disk = {
                    'labels': [""] * 10,
                    'datasets': [
                        {
                            "fillColor": "rgba(83,191,189,0.5)",
                            "strokeColor": "rgba(83,191,189,1)",
                            "pointColor": "rgba(83,191,189,1)",
                            "pointStrokeColor": "#fff",
                            "data": datasets_rd
                        },
                        {
                            "fillColor": "rgba(249,134,33,0.5)",
                            "strokeColor": "rgba(249,134,33,1)",
                            "pointColor": "rgba(249,134,33,1)",
                            "pointStrokeColor": "#fff",
                            "data": datasets_wr
                        },
                    ]
                }

            json_blk.append({'dev': blk['dev'], 'data': disk})
            cookie_blk[blk['dev']] = [datasets_rd, datasets_wr]

        for net in net_usage:
            if cookies['net'] == '{}' or not cookies['net'] or not net_usage:
                datasets_rx.append(0)
                datasets_tx.append(0)
            else:
                datasets['net'] = eval(cookies['net'])
                try:
                    datasets_rx = datasets['net'][net['dev']][0]
                    datasets_tx = datasets['net'][net['dev']][1]
                except:
                    net_error = True

            if not net_error:
                if len(datasets_rx) > 10:
                    while datasets_rx:
                        del datasets_rx[0]
                        if len(datasets_rx) == 10:
                            break
                if len(datasets_tx) > 10:
                    while datasets_tx:
                        del datasets_tx[0]
                        if len(datasets_tx) == 10:
                            break

                if len(datasets_rx) <= 9:
                    datasets_rx.append(int(net['rx']) / 1048576)
                if len(datasets_rx) == 10:
                    datasets_rx.append(int(net['rx']) / 1048576)
                    del datasets_rx[0]

                if len(datasets_tx) <= 9:
                    datasets_tx.append(int(net['tx']) / 1048576)
                if len(datasets_tx) == 10:
                    datasets_tx.append(int(net['tx']) / 1048576)
                    del datasets_tx[0]

                network = {
                    'labels': [""] * 10,
                    'datasets': [
                        {
                            "fillColor": "rgba(83,191,189,0.5)",
                            "strokeColor": "rgba(83,191,189,1)",
                            "pointColor": "rgba(83,191,189,1)",
                            "pointStrokeColor": "#fff",
                            "data": datasets_rx
                        },
                        {
                            "fillColor": "rgba(151,187,205,0.5)",
                            "strokeColor": "rgba(151,187,205,1)",
                            "pointColor": "rgba(151,187,205,1)",
                            "pointStrokeColor": "#fff",
                            "data": datasets_tx
                        },
                    ]
                }

            json_net.append({'dev': net['dev'], 'data': network})
            cookie_net[net['dev']] = [datasets_rx, datasets_tx]

        data = json.dumps({'status': status, 'cpu': cpu, 'hdd': json_blk, 'net': json_net})
    else:
        datasets = [0] * 10
        cpu = {
            'labels': [""] * 10,
            'datasets': [
                {
                    "fillColor": "rgba(241,72,70,0.5)",
                    "strokeColor": "rgba(241,72,70,1)",
                    "pointColor": "rgba(241,72,70,1)",
                    "pointStrokeColor": "#fff",
                    "data": datasets
                }
            ]
        }

        for i, net in enumerate(networks):
            datasets_rx = [0] * 10
            datasets_tx = [0] * 10
            network = {
                'labels': [""] * 10,
                'datasets': [
                    {
                        "fillColor": "rgba(83,191,189,0.5)",
                        "strokeColor": "rgba(83,191,189,1)",
                        "pointColor": "rgba(83,191,189,1)",
                        "pointStrokeColor": "#fff",
                        "data": datasets_rx
                    },
                    {
                        "fillColor": "rgba(151,187,205,0.5)",
                        "strokeColor": "rgba(151,187,205,1)",
                        "pointColor": "rgba(151,187,205,1)",
                        "pointStrokeColor": "#fff",
                        "data": datasets_tx
                    },
                ]
            }
            json_net.append({'dev': i, 'data': network})

        for blk in disks:
            datasets_wr = [0] * 10
            datasets_rd = [0] * 10
            disk = {
                'labels': [""] * 10,
                'datasets': [
                    {
                        "fillColor": "rgba(83,191,189,0.5)",
                        "strokeColor": "rgba(83,191,189,1)",
                        "pointColor": "rgba(83,191,189,1)",
                        "pointStrokeColor": "#fff",
                        "data": datasets_rd
                    },
                    {
                        "fillColor": "rgba(249,134,33,0.5)",
                        "strokeColor": "rgba(249,134,33,1)",
                        "pointColor": "rgba(249,134,33,1)",
                        "pointStrokeColor": "#fff",
                        "data": datasets_wr
                    },
                ]
            }
            json_blk.append({'dev': blk['dev'], 'data': disk})
        data = json.dumps({'status': status, 'cpu': cpu, 'hdd': json_blk, 'net': json_net})

    response = HttpResponse()
    response['Content-Type'] = "text/javascript"
    if status == 1:
        response.cookies['cpu'] = datasets['cpu']
        response.cookies['hdd'] = cookie_blk
        response.cookies['net'] = cookie_net
    response.write(data)
    return response


def insts_status(request, host_id):
    """
    Instances block
    """
    errors = []
    instances = []
    compute = Compute.objects.get(id=host_id)

    try:
        conn = wvmInstances(compute.hostname,
                            compute.login,
                            compute.password,
                            compute.type)
        get_instances = conn.get_instances()
    except libvirtError as err:
        errors.append(err)

    for instance in get_instances:
        instances.append({'name': instance,
                          'status': conn.get_instance_status(instance),
                          'memory': conn.get_instance_memory(instance),
                          'vcpu': conn.get_instance_vcpu(instance),
                          'uuid': conn.get_uuid(instance),
                          'host': host_id,
                          'dump': conn.get_instance_managed_save_image(instance)
                          })

    data = json.dumps(instances)
    response = HttpResponse()
    response['Content-Type'] = "text/javascript"
    response.write(data)
    return response


def instances(request, host_id):
    """
    Instances block
    """
    errors = []
    instances = []
    time_refresh = 8000
    get_instances = []
    conn = None
    compute = Compute.objects.get(id=host_id)

    try:
        conn = wvmInstances(compute.hostname,
                            compute.login,
                            compute.password,
                            compute.type)
        get_instances = conn.get_instances()
    except libvirtError as err:
        errors.append(err)

    for instance in get_instances:
        try:
            inst = Instance.objects.get(compute_id=host_id, name=instance)
            uuid = inst.uuid
        except Instance.DoesNotExist:
            uuid = conn.get_uuid(instance)
            inst = Instance(compute_id=host_id, name=instance, uuid=uuid)
            inst.save()

        conn2 = wvmInstance(compute.hostname,
            compute.login,
            compute.password,
            compute.type,
            instance)

        instances.append({'name': instance,
                          'status': conn.get_instance_status(instance),
                          'uuid': uuid,
                          'memory': conn.get_instance_memory(instance),
                          'vcpu': conn.get_instance_vcpu(instance),
                          'storage': conn2.get_disk_device(),
                          'has_managed_save_image': conn.get_instance_managed_save_image(instance)})

        conn2.close()

    if conn:
        try:
            if request.method == 'POST':
                name = request.POST.get('name', '')
                if 'start' in request.POST:
                    conn.start(name)
                    return HttpResponseRedirect(request.get_full_path())
                if 'shutdown' in request.POST:
                    conn.shutdown(name)
                    return HttpResponseRedirect(request.get_full_path())
                if 'destroy' in request.POST:
                    conn.force_shutdown(name)
                    return HttpResponseRedirect(request.get_full_path())
                if 'managedsave' in request.POST:
                    conn.managedsave(name)
                    return HttpResponseRedirect(request.get_full_path())
                if 'deletesaveimage' in request.POST:
                    conn.managed_save_remove(name)
                    return HttpResponseRedirect(request.get_full_path())
                if 'suspend' in request.POST:
                    conn.suspend(name)
                    return HttpResponseRedirect(request.get_full_path())
                if 'resume' in request.POST:
                    conn.resume(name)
                    return HttpResponseRedirect(request.get_full_path())

            conn.close()
        except libvirtError as err:
            errors.append(err)

    object = {
        'response': {
            'instances': instances
        },
        'errors': [str(error) for error in errors]
    }
    return render(object, 'instances.html', locals(), request)


def instance_status(request):
    payload = json.loads(request.body)
    machines = []
    def query_hypervisor(hostnames):
        compute = Compute.objects.get(id=host_id)

        object = {}
        def query_machine(hostname):
            try:
                conn = wvmInstance(compute.hostname,
                                   compute.login,
                                   compute.password,
                                   compute.type, hostname)
                object[hostname] = {
                    'status': conn.get_status(),
                    'cur_memory': conn.get_cur_memory(),
                    'disks': conn.get_disk_device(),
                    'vcpu': conn.get_vcpu()
                }
            except libvirtError:
                status = None
        pool = ThreadPool(min(len(hostnames), 20))
        for hostname in hostnames:
            pool.add_task(query_machine, hostname)
        pool.wait_completion()

        for key in object:
            val = object[key]
            val['hostname'] = key
            val['hypervisor_id'] = host_id
            machines.append(val)

    pool = ThreadPool(min(len(payload), 10))
    for host_id in payload:
        pool.add_task(query_hypervisor, payload[host_id])
    pool.wait_completion()

    return render({'response': {'machines': machines}}, 'instance.html', locals(), request)

def instance(request, host_id, vname):
    """
    Instance block
    """
    def show_clone_disk(disks):
        clone_disk = []
        for disk in disks:
            if disk['image'].count(".") and len(disk['image'].rsplit(".", 1)[1]) <= 7:
                name, suffix = disk['image'].rsplit(".", 1)
                image = name + "-clone" + "." + suffix
            else:
                image = disk['image'] + "-clone"
            clone_disk.append(
                {'dev': disk['dev'], 'storage': disk['storage'], 'image': image, 'format': disk['format']})
        return clone_disk

    errors = []
    messages = []
    time_refresh = TIME_JS_REFRESH
    compute = Compute.objects.get(id=host_id)
    computes = Compute.objects.all()
    computes_count = len(computes)
    keymaps = QEMU_KEYMAPS
    try:
        conn = wvmInstance(compute.hostname,
                           compute.login,
                           compute.password,
                           compute.type,
                           vname)


        params = {
            'status': 'get_status',
            'vcpu': 'get_vcpu',
            'cur_vcpu': 'get_cur_vcpu',
            'uuid': 'get_uuid',
            'memory': 'get_memory',
            'cur_memory': 'get_cur_memory',
            'description': 'get_description',
            'disks': 'get_disk_device',
            'media': 'get_media_device',
            'vcpu_range': 'get_max_cpus',
            'max_memory': 'get_max_memory',
            'vnc_port': 'get_vnc_port',
            'vnc_keymap': 'get_vnc_keymap',
            'vnc_passwd': 'get_vnc_passwd',
        }
        object = {}
        def get_param(param, tocall):
            object[param] = getattr(conn, tocall)()
        mypool = ThreadPool(5)
        for param in params:
            mypool.add_task(get_param, param, params[param])
        mypool.wait_completion()

        # status = conn.get_status()
        status = object['status']
        autostart = 0 #conn.get_autostart()
        # vcpu = conn.get_vcpu()
        vcpu = object['vcpu']
        # cur_vcpu = conn.get_cur_vcpu()
        cur_vcpu = object['cur_vcpu']
        # uuid = conn.get_uuid()
        uuid = object['uuid']
        # memory = conn.get_memory()
        memory = object['memory']
        # cur_memory = conn.get_cur_memory()
        cur_memory = object['cur_memory']
        # description = conn.get_description()
        description = object['description']
        # disks = conn.get_disk_device()
        disks = object['disks']
        # media = conn.get_media_device()
        media = object['media']
        networks = ''#conn.get_net_device()
        media_iso = []#sorted(conn.get_iso_media())
        # vcpu_range = conn.get_max_cpus()
        vcpu_range = object['vcpu_range']

        memory_range = [256, 512, 1024, 2048, 4096, 6144, 8192, 16384]
        # memory_host = conn.get_max_memory()
        memory_host = object['max_memory']
        vcpu_host = len(vcpu_range)
        telnet_port = 0#conn.get_telnet_port()
        # vnc_port = conn.get_vnc_port()
        vnc_port = object['vnc_port']
        # vnc_keymap = conn.get_vnc_keymap()
        vnc_keymap = object['vnc_keymap']
        vnc_password = object['vnc_passwd']
        snapshots = []#sorted(conn.get_snapshot(), reverse=True)
        inst_xml = ''#conn._XMLDesc(VIR_DOMAIN_XML_SECURE)
        has_managed_save_image = 0#conn.get_managed_save_image()
        clone_disks = []#show_clone_disk(disks)
        cpu_usage = 0#conn.raw_cpu_usage()
    except libvirtError as err:
        errors.append(err)

    try:
        instance = Instance.objects.get(compute_id=host_id, name=vname)
        if instance.uuid != uuid:
            instance.uuid = uuid
            instance.save()
    except Instance.DoesNotExist:
        instance = Instance(compute_id=host_id, name=vname, uuid=uuid)
        instance.save()

    try:
        if request.method == 'POST':
            if 'start' in request.POST:
                conn.start()
                return HttpResponseRedirect(request.get_full_path() + '#shutdown')
            if 'power' in request.POST:
                if 'shutdown' == request.POST.get('power', ''):
                    conn.shutdown()
                    return HttpResponseRedirect(request.get_full_path() + '#shutdown')
                if 'destroy' == request.POST.get('power', ''):
                    conn.force_shutdown()
                    return HttpResponseRedirect(request.get_full_path() + '#forceshutdown')
                if 'managedsave' == request.POST.get('power', ''):
                    conn.managedsave()
                    return HttpResponseRedirect(request.get_full_path() + '#managedsave')
            if 'deletesaveimage' in request.POST:
                conn.managed_save_remove()
                return HttpResponseRedirect(request.get_full_path() + '#managedsave')
            if 'suspend' in request.POST:
                conn.suspend()
                return HttpResponseRedirect(request.get_full_path() + '#suspend')
            if 'resume' in request.POST:
                conn.resume()
                return HttpResponseRedirect(request.get_full_path() + '#suspend')
            if 'delete' in request.POST:
                if conn.get_status() == 1:
                    conn.force_shutdown()
                if request.POST.get('delete_disk', ''):
                    conn.delete_disk()
                try:
                    instance = Instance.objects.get(compute_id=host_id, name=vname)
                    instance.delete()
                finally:
                    conn.delete()
                return HttpResponseRedirect('/%s/instances' % host_id)
            if 'assign_volume' in request.POST:
                file = request.POST.get('file', '')
                device = request.POST.get('device', '')
                conn.assign_volume(file, device)
                return HttpResponseRedirect(request.get_full_path() + '#instancedevice')
            if 'unassign_volume' in request.POST:
                device = request.POST.get('device', '')
                conn.unassign_volume(device)
                return HttpResponseRedirect(request.get_full_path() + '#instancedevice')
            if 'snapshot' in request.POST:
                name = request.POST.get('name', '')
                conn.create_snapshot(name)
                return HttpResponseRedirect(request.get_full_path() + '#istaceshapshosts')
            if 'external_storage_snapshot' in request.POST:
                name = request.POST.get('name', '')
                conn.create_external_storage_snapshot(name)
                return HttpResponseRedirect(request.get_full_path() + '#istaceshapshosts')
            if 'umount_iso' in request.POST:
                image = request.POST.get('path', '')
                first_cd = media[0]['dev'] if len(media) > 0 else request.POST.get('umount_iso', '')
                dev = request.POST.get('device', first_cd)
                conn.umount_iso(dev, image)
                return HttpResponseRedirect(request.get_full_path() + '#instancemedia')
            if 'mount_iso' in request.POST:
                image = request.POST.get('media', '')
                first_cd = media[0]['dev'] if len(media) > 0 else ''
                dev = request.POST.get('device', first_cd)
                conn.mount_iso(dev, image)
                return HttpResponseRedirect(request.get_full_path() + '#instancemedia')
            if 'set_autostart' in request.POST:
                conn.set_autostart(1)
                return HttpResponseRedirect(request.get_full_path() + '#instancesettings')
            if 'unset_autostart' in request.POST:
                conn.set_autostart(0)
                return HttpResponseRedirect(request.get_full_path() + '#instancesettings')
            if 'change_settings' in request.POST:
                description = request.POST.get('description', '')
                vcpu = request.POST.get('vcpu', '')
                cur_vcpu = request.POST.get('cur_vcpu', '')
                memory = request.POST.get('memory', '')
                cur_memory = request.POST.get('cur_memory', '')
                conn.change_settings(description, cur_memory, memory, cur_vcpu, vcpu)
                return HttpResponseRedirect(request.get_full_path() + '#instancesettings')
            if 'change_xml' in request.POST:
                xml = request.POST.get('inst_xml', '')
                if xml:
                    conn._defineXML(xml)
                    return HttpResponseRedirect(request.get_full_path() + '#instancexml')
            if 'set_vnc_passwd' in request.POST:
                if request.POST.get('auto_pass', ''):
                    passwd = ''.join([choice(letters + digits) for i in xrange(12)])
                else:
                    passwd = request.POST.get('vnc_passwd', '')
                    clear = request.POST.get('clear_pass', False)
                    if not passwd and not clear:
                        msg = _("Enter the VNC password or select Generate")
                        errors.append(msg)
                if not errors:
                    conn.set_vnc_passwd(passwd)
                    return HttpResponseRedirect(request.get_full_path() + '#vnc_pass')

            if 'set_vnc_keymap' in request.POST:
                keymap = request.POST.get('vnc_keymap', '')
                clear = request.POST.get('clear_keymap', False)
                if clear:
                    conn.set_vnc_keymap('')
                else:
                    conn.set_vnc_keymap(keymap)
                return HttpResponseRedirect(request.get_full_path() + '#vnc_keymap')

            if 'migrate' in request.POST:
                compute_id = request.POST.get('compute_id', '')
                live = request.POST.get('live_migrate', False)
                unsafe = request.POST.get('unsafe_migrate', False)
                xml_del = request.POST.get('xml_delete', False)
                new_compute = Compute.objects.get(id=compute_id)
                conn_migrate = wvmInstances(new_compute.hostname,
                                            new_compute.login,
                                            new_compute.password,
                                            new_compute.type)
                conn_migrate.moveto(conn, vname, live, unsafe, xml_del)
                conn_migrate.define_move(vname)
                conn_migrate.close()
                return HttpResponseRedirect('/%s/instance/%s' % (compute_id, vname))
            if 'delete_snapshot' in request.POST:
                snap_name = request.POST.get('name', '')
                conn.snapshot_delete(snap_name)
                return HttpResponseRedirect(request.get_full_path() + '#istaceshapshosts')
            if 'revert_snapshot' in request.POST:
                snap_name = request.POST.get('name', '')
                conn.snapshot_revert(snap_name)
                msg = _("Successful revert snapshot: ")
                msg += snap_name
                messages.append(msg)
            if 'clone' in request.POST:
                clone_data = {}
                clone_data['name'] = request.POST.get('name', '')

                for post in request.POST:
                    if 'disk' or 'meta' in post:
                        clone_data[post] = request.POST.get(post, '')

                conn.clone_instance(clone_data)
                return HttpResponseRedirect('/%s/instance/%s' % (host_id, clone_data['name']))

        conn.close()

    except libvirtError as err:
        errors.append(err)

    object = {
        'errors': [str(error) for error in errors],
        'response': {
            'name': vname,
            'status': status,
            'autostart': autostart,
            'vcpu': vcpu,
            'cur_vcpu': cur_vcpu,
            'uuid': uuid,
            'memory': memory,
            'cur_memory': cur_memory,
            'description': description,
            'disks': disks,
            'media': media,
            'networks': networks,
            'media_iso': media_iso,
            'vcpu_range': vcpu_range.__len__(),
            'memory_host': memory_host,
            'vcpu_host': vcpu_host,
            'telnet_port': telnet_port,
            'vnc_port': vnc_port,
            'vnc_keymap': vnc_keymap,
            'snapshots': snapshots,
            'inst_xml': inst_xml.__str__(),
            'has_managed_save_image': has_managed_save_image,
            'clone_disks': clone_disks,
            'cpu_usage': cpu_usage,
            'vnc_password': vnc_password
        }
    }
    return render(object, 'instance.html', locals(), request)
