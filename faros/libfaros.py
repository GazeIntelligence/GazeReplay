# This file is part of Faros Streamer.
#
# Copyright 2015
# Andreas Henelius <andreas.henelius@ttl.fi>,
# Finnish Institute of Occupational Health
#
# This code is released under the MIT License
# http://opensource.org/licenses/mit-license.php
#
# Please see the file LICENSE for details.

import os
import sys
import bluetooth

from construct import Struct, Byte, BitStruct, Int32ul, Array, Int16sl
from collections import OrderedDict
import struct
import time
from pylsl import StreamOutlet, StreamInfo
import hashlib
import threading

from . import crc16pure as crc16

# -------------------------------------------------------------------------------
# Functions for printing
# -------------------------------------------------------------------------------

def print_devices(x):
    """ Helper function for printing device list. """
    for i in x:
        print(i + "\t" + x[i])


def sync_time(s):
    print("-" * 45)
    print("Synchronising time")
    print("-" * 45)
    print_kv("Old time", get_device_time(s))
    set_device_time(s)
    print_kv("New time", get_device_time(s))
    print("-" * 45)
    print("")

def get_devices():
    """ Search for bluetooth devices and return
        a dictionary with the names and bluetooth addresses
        of the found devices.
    """
    print("Scanning for available devices.")
    try:
        nearby_devices = bluetooth.discover_devices()
    except OSError:
        raise Exception("Could not find local Bluetooth device. Are you sure Bluetooth is turned on on your computer ?")
    out = {}
    for bdaddr in nearby_devices:
        name = bluetooth.lookup_name(bdaddr)
        out[name] = bdaddr
    if out is not None:
        print("Found the following devices:")
        print_devices(out)
        print("")
    else:
        print("Found no devices.")
    return(out)


def print_kv(k, v, pad = 25, pc = " "):
    """ Print key-value pairs with padding. """
    print(k.ljust(pad, pc), v)

    
def print_header(x, pad = 25, pc = " "):
    """ Print table headers with padding. """
    str = ''
    for i in x:
        str += i.ljust(pad, pc)
    print(str)


def print_properties(x):
    """ Print a formatted list of the settings
        of a Faros device.
    """
    settings = unpack_settings(x['settings'])

    print("-" * 45)
    print("Device settings")
    print("-" * 45)
    print_kv("Name", x['name'])
    print_kv("Firmware version", x['firmware-version'])
    print_kv("Firmware build date", x['firmware-build'])
    print("")
    print_kv("No. of ECG channels", settings['n_ecg'])
    print_kv("ECG sampling rate", settings['ecg_fs'])
    print_kv("ECG resolution (uV)", settings['ecg_res'])
    print_kv("ECG highpass filter (Hz)", settings['ecg_hp'])
    print_kv("RR interval recording", settings['ecg_rr'])
    print("")
    print_kv("Acc sampling rate", settings['acc_fs'])
    print_kv("Acc resolution (uV)", settings['acc_res'])
    print("")
    print_kv("Temperature recording", settings['temperature'])
    print("")
    print_kv("Device time:", binary_time_to_str(x['device_time']))
    print("-" * 45)
    print("")

# -------------------------------------------------------------------------------
# Functions for getting and manipulating device properties (settings)
# -------------------------------------------------------------------------------

def get_properties(s):
    """ Get properties (name, firmware veersion and build date, and settings)
        of a Faros device connected to socket s.
    """
    properties = ['name', 'firmware-version', 'firmware-build', 'device_time', 'settings']
    out = {}
    for p in properties:
        out[p] = get_property(s, p)

    return(out)


def get_ecg_str_fs(s = None):
    """ Return ECG sampling rate given character. """
    x =  {'0' : 0,
          '1' : 1000,
          '2' : 500,
          '4' : 250,
          '8' : 125}
    if s is None:
        return x
    else:
        return x[str(s)]

    
def get_ecg_str_res(s = None):
    """ Return ECG resolution given character. """
    x = {'0' : 0.25, '1' : 1}
    if s is None:
        return x
    else:
        return x[str(s)]

def get_ecg_str_hp(s = None):
    """ Get ECG high-pass filter given character. """
    x = {'0' : 0.05, '1' : 10}
    if s is None:
        return x
    else:
        return x[str(s)]
    

def get_ecg_str_rr(s = None):
    """ Are RR-intervals recorded or not (given string). """
    x = {'0' : 'off', '1' : 'on'}
    if s is None:
         return x
    else:
        return x[str(s)]


def get_acc_str_fs(s = None):
    """ Get accelerometer sampling rate given character. """
    x = {'0' : 0,
         '1' : 100,
         '4' : 25}
    
    if s is None:
        return x
    else:
        return x[str(s)]

    
def get_acc_str_res(s = None):
    """ Get accelerometer resolution given character. """
    x = {'0' : 0.25,
         '1' : 1,
         '2' : 0.5}
    if s is None:
        return x
    else:
        return x[str(s)]
    

def get_temp_str(s):
    """ Is temperature recorded or not (given string). """
    return {'0' : 'off', '1' : 'on'}[s]


def get_packet_size(settings):
    """ Return the packet size given the settings of the device. """
    n_ecg_s = int(settings['ecg_fs']) / 5
    n_acc_s = int(settings['acc_fs']) / 5

    ecg_s   = 2 * int(settings['n_ecg']) * n_ecg_s
    acc_s   = 6 *n_acc_s
    
    ps = 26
    ps += ecg_s
    ps += acc_s

    if settings['ecg_rr'] == 'on':
        ps += 2
        n_rr_s = 1
    else:
        n_rr_s = 0

    if settings['temperature'] == 'on':
        ps += 2
        n_temp_s = 1
    else:
        n_temp_s = 0

    # make frame length divisible by 4
    if (ps % 4) != 0:
        ps += 2
        n_padd = 1
    else:
        n_padd = 0

    out = {'ps'       : int(ps),
           'ecg_ps'   : int(ecg_s),
           'acc_ps'   : int(acc_s),
           'n_ecg_c'  : int(settings['n_ecg']),
           'n_ecg_s'  : int(n_ecg_s),
           'n_acc_s'  : int(n_acc_s),
           'n_rr_s'   : int(n_rr_s),
           'n_temp_s' : int(n_temp_s),
           'n_padd'   : int(n_padd)}
        
    return(out)
    

def inv_lookup(d, v):
    """ Helper function for performing a reverse dictionary lookup. """
    invd = {str(v): str(k) for k, v in d.items()}
    return invd[str(v)]

    
def mode_to_str(ecg_n   = '1',
                ecg_fs  = '100',
                ecg_res = '1',
                ecg_hp  = '0.05',
                rr      = '0',
                acc_fs  = '100',
                acc_res = '1',
                temp    = '0'):
    """ Given settings (sampling rates, resolutions etc), Return the settings
        of a Faros device as a string.
    """
    ecg_fs  = inv_lookup(get_ecg_str_fs(), ecg_fs)
    ecg_res = inv_lookup(get_ecg_str_res(), ecg_res)
    ecg_hp  = inv_lookup(get_ecg_str_hp(), ecg_hp)

    acc_fs  = inv_lookup(get_acc_str_fs(), acc_fs)
    acc_res = inv_lookup(get_acc_str_res(), acc_res)
    
    vals = [ecg_n, ecg_fs, ecg_res, ecg_hp, rr, acc_fs, acc_res, temp]
    res  = ''.join([str(i) for i in vals])

    return(res)


def unpack_settings(s):
    """ Unpack the settings as one 8-character
        string.
    """
    s = s[3:]
    out = {'n_ecg'       : s[0],
           'ecg_fs'      : get_ecg_str_fs(s[1]),
           'ecg_res'     : get_ecg_str_res(s[2]),
           'ecg_hp'      : get_ecg_str_hp(s[3]),
           'ecg_rr'      : get_ecg_str_rr(s[4]),
           
           'acc_fs'      : get_acc_str_fs(s[5]),
           'acc_res'     : get_acc_str_res(s[6]),
           
           'temperature' : get_temp_str(s[7])}
    return(out)


# -------------------------------------------------------------------------------
# Functions for communicating with the Faros device
# -------------------------------------------------------------------------------

def connect(addr):
    """ Connect to a device using the bluetooth address addr. """
    port = 1
    
    #if its a second gen device get the right port for it
    services = bluetooth.find_service(address = addr)
    
    for serv in services:
        if serv["name"] == b'Bluetooth Serial Port' or serv["name"] == 'Bluetooth Serial Port' :
            port = serv["port"]  
	    
    s = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    print(f"connecting to port {port} with address {addr}")
    s.connect((addr, port))
    print("connection finished")
    return(s)


def disconnect(s):
    """ Disconnect from socket s. """
    s.close()

    
def send_command(s, command, r_length = 0, decode = True):
    """ Send a command to a Faros device.

        s        : the socket to send to
        command  : the command to send
        r_length : response length (if any). Default is 0 (no response)
        decode   : should the response data be decoded to ASCII
    """
    data = None
    s.send(command + '\r')

    if r_length:
        data = s.recv(r_length)
        if decode:
            try:
                data = data.decode("UTF-8").strip()
            except UnicodeDecodeError:
                data = None
    return(data)


def get_property(s, p):
    """ Get property p from socket s.
        p can be 'firmware-version', 'firmware'build', 'name'
        or 'settings'.
    """
    prop_map = {'firmware-version': ['wbainf', 9, True],
                'firmware-build': ['wbaind', 9, True],
                'name' : ['wbawho', 12, True],
                'device_time' : ['wbagdt', 8, False],
                'settings' : ['wbagds', 12, True]}

    if p in prop_map.keys():
        res = send_command(s, prop_map[p][0], prop_map[p][1], prop_map[p][2])
        
        if res is not None:
            if (p == 'name') and res.startswith('FAROS'):
                    res += s.recv(2).decode("UTF-8").strip()
        return res
    else:
        return None

def set_device_time(s):
    """ Set current device time. """
    current_time = int(time.time())
    current_time += (-time.timezone)

    ct_bytes = struct.pack('i', current_time)

    s.send('wbasdt')
    s.send(ct_bytes)
    s.send('\r')

    data = s.recv(7)
    return data

def binary_time_to_unix_time(x):
    """ Convert Faros binary time to UNIX time. """
    device_time_bytes = x[3:].strip()
    return float(struct.unpack("<L", device_time_bytes)[0])

def unix_time_to_ts(x):
    """ Return the current time as a string. """
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(x))

def binary_time_to_str(x):
    """ Convert Faros binary time to a string. """
    return unix_time_to_ts(binary_time_to_unix_time(x))

def get_device_time(s):
    """ Get current device time. """
    s.send('wbagdt' + '\r')
    data = s.recv(8)
    
    return binary_time_to_str(data)
    

# -------------------------------------------------------------------------------
# Unpack the data received from a Faros device
# -------------------------------------------------------------------------------

def unpack_data(packet,
                packet_size,
                p_header,

                p_ecg         = None,
                p_acc         = None,
                p_marker      = None,
                p_rr          = None,
                p_temp        = None,
          
                outlet_ecg    = None,
                outlet_acc    = None,
                outlet_marker = None,
                outlet_rr     = None,
                outlet_temp   = None):
    """ Unpack data read from a Faros device and
        stream the data over the Lab Streaming Layer
        (LSL).
    """
    
    # (0) ----- Header -----
    header = p_header.parse(packet[0:8])

    # (1) ----- ECG -----
    if p_ecg is not None:
        ecg = p_ecg.parse(packet[8:(8 + packet_size['ecg_ps'])])['ecg']

        if int(packet_size['n_ecg_c']) > 1:
            ecg = [ecg[i::packet_size['n_ecg_s']] for i in range(packet_size['n_ecg_s'])]
        

    if outlet_ecg is not None:
        outlet_ecg.push_chunk(ecg)

    # (2) ----- Accelerometer -----
    if p_acc is not None:
        acc = p_acc.parse(packet[(8 + packet_size['ecg_ps']):(8 + packet_size['ecg_ps'] + packet_size['acc_ps'])])['acc']
        acc = [acc[i::packet_size['n_acc_s']] for i in range(packet_size['n_acc_s'])]

    if outlet_acc is not None:
        outlet_acc.push_chunk(acc)

    # (3) ----- Marker -----
    if outlet_marker is not None:
        b1 = 8 + packet_size['ecg_ps'] + packet_size['acc_ps']
        b2 = b1 + 2
        marker = p_marker.parse(packet[b1:b2])['marker']
        if marker[0] > 0:
            outlet_marker.push_sample([1])

    # (4) ----- RR -----
    if p_rr is not None:
        b1 = 10 + packet_size['ecg_ps'] + packet_size['acc_ps']
        b2 = b1 + 2
        rr = p_rr.parse(packet[b1:b2])['rr'][0]
        if header['flag']['rr_in_packet']:
            outlet_rr.push_sample([rr])
        
    # (5) ----- Temperature -----
    if p_temp is not None:
        b1 = 10 + packet_size['ecg_ps'] + packet_size['acc_ps'] + 2 * packet_size['n_rr_s']
        b2 = b1 + 2
        temp = p_temp.parse(packet[b1:b2])['temp'][0]
        # convert raw ADC values to degrees Celsius
        temp = temp * (-(158.3488 + 53.3361)/4095) + 158.3488
        outlet_temp.push_sample([temp])

    # (6) ----- The packet checksum -----
    #
    # p_crc = Struct('packet_format', Array(1, ULInt16('crc')))
    # crc   = p_crc.parse(packet[-2:])['crc'][0]
    # crc2  = crc16.crc16xmodem(packet[:-2])
    # print(crc - crc2)
    
    
# -------------------------------------------------------------------------------
# Define Faros packet formats
# -------------------------------------------------------------------------------

def get_packet_header():
    
        return Struct(
            "sig_1" / Byte,
            "sig_2" / Byte,
            "sig_3" / Byte,
            "flag" / BitStruct(
                "battery_h" / Byte,
                "battery_l" / Byte,
                "rr_error" / Byte,
                "dummy_4" / Byte,
                "dummy_3" / Byte,
                "dummy_2" / Byte,
                "dummy_1" / Byte,
                "rr_in_packet" / Byte),
            "packet_number" / Int32ul)


def get_data_packet(N, name):
    return Struct(name / Array(N, Int16sl))

def create_lsl_outlet(stream_name, stream_type, channel_count, sampling_rate, channel_format = 'int16', get_info = False):
    """ Create an LSL outlet. """
    stream_id = hashlib.md5(stream_name.encode("ascii")).hexdigest()[1:10]
    info      = StreamInfo(name           = stream_name,
                           type           = stream_type,
                           channel_count  = channel_count,
                           nominal_srate  = sampling_rate,
                           channel_format = channel_format,
                           source_id      = stream_id)
    return StreamOutlet(info, max_buffered = 1)

    
def configure_device(socket, settings):
    """ Configure a Faros device by sending all settings as one string. """
    ## example : settings = '32100t00'
    command = 'wbasds' + settings
    res = send_command(socket, command, r_length = 7)
    if res == 'wbaack':
        print("Settings successfully stored.")
    else:
        print("Error! Settings not stored.")

class StreamerThread(threading.Thread):
    """ Read data from a Faros device and stream the data using
        the Lab Streaming Layer (LSL).
    """
    def __init__(self, stream_data,
                 faros_socket,
                 packet_size,

                 p_header,
                 p_ecg,
                 p_acc,
                 p_marker,
                 p_rr,
                 p_temp,
                 
                 outlet_ecg,
                 outlet_acc,
                 outlet_marker,
                 outlet_rr,
                 outlet_temp):
        
        threading.Thread.__init__(self)
        self.stream_data  = stream_data
        self.faros_socket = faros_socket
        self.packet_size  = packet_size

        self.p_header     = p_header
        self.p_ecg        = p_ecg
        self.p_acc        = p_acc
        self.p_marker     = p_marker
        self.p_rr         = p_rr
        self.p_temp       = p_temp

        self.outlet_ecg    = outlet_ecg
        self.outlet_acc    = outlet_acc
        self.outlet_marker = outlet_marker
        self.outlet_rr     = outlet_rr
        self.outlet_temp   = outlet_temp
        
        self.outlets = [self.outlet_ecg,self.outlet_acc,self.outlet_marker, self.outlet_rr, self.outlet_temp]

    def run(self):
        self.stream_data = True

        ps        = self.packet_size['ps']
        read_size = 300
        np        = 0
        data      = b''

        command = "wbaoms"
        res     = send_command(self.faros_socket, command, 7)

        command = "wbaom7"
        res     = send_command(self.faros_socket, command, 7)

        p_crc = Struct('crc' /  Array(1, Int16sl))

        self.faros_socket.setblocking(True)

        while (self.stream_data):
            data += self.faros_socket.recv(read_size)
            
            if len(data) >= ps:

                packet    = data[0:ps]
                data      = data[ps:]
                signature = packet[0:3]
                
                try:
                    crc_1     = p_crc.parse(packet[-2:])['crc'][0]
                    crc_2     = crc16.crc16xmodem(packet[:-2])
                except TypeError:
                    crc_1 = 0
                    crc_2 = 1

                #if (signature == b'MEP') & (crc_1 == crc_2):
                if True:

                    unpack_data(packet        = packet,
                                packet_size   = self.packet_size,

                                p_header      = self.p_header,
                                p_ecg         = self.p_ecg,
                                p_acc         = self.p_acc,
                                p_marker      = self.p_marker,
                                p_rr          = self.p_rr,
                                p_temp        = self.p_temp,

                                outlet_ecg    = self.outlet_ecg,
                                outlet_acc    = self.outlet_acc,
                                outlet_marker = self.outlet_marker,
                                outlet_rr     = self.outlet_rr,
                                outlet_temp   = self.outlet_temp)
                    # np += 1
                else:
                    while True:
                        tmp = self.faros_socket.recv(read_size)
                        if tmp[0:3] == b'MEP':
                            data = tmp
                            break


    def stop(self):
        self.stream_data = False
        command = "wbaoms"
        #send_command(self.faros_socket, command, 0)

def stream_lsl(sock, active_streams, settings, device_name = None):
    ## get the settings
    """
    properties  = get_properties(sock)
    settings  = unpack_settings(properties['settings'])
    """
    packet_size = get_packet_size(settings)
    
    # Get packet formats and create LSL outlets
    p_header = get_packet_header()
    
    # (1) ----- ECG -----
    if packet_size['n_ecg_s'] > 0 and 'ECG' in active_streams:
        p_ecg            = get_data_packet((packet_size['n_ecg_c'] * packet_size['n_ecg_s']), 'ecg')
        sn               = 'faros_ECG' if device_name is None else device_name+'_ECG'
        faros_outlet_ecg = create_lsl_outlet(sn, 'ECG', packet_size['n_ecg_c'], settings['ecg_fs'], channel_format = 'int16')
    else:
        p_ecg            = None
        faros_outlet_ecg = None
        
    # (2) ----- Acc -----
    if packet_size['n_acc_s'] > 0 and 'acc' in active_streams:
        p_acc            = get_data_packet(3 * packet_size['n_acc_s'], 'acc')
        sn               = 'faros_acc' if device_name is None else device_name+'_acc'
        faros_outlet_acc = create_lsl_outlet(sn, 'Acc', 3, settings['acc_fs'], channel_format = 'int16')
    else:
        p_acc            = None
        faros_outlet_acc = None
        
    # (3) ----- Marker -----
    if 'marker' in active_streams:
        p_marker            = get_data_packet(1, 'marker')
        sn                  = 'faros_marker' if device_name is None else device_name+'_marker'
        faros_outlet_marker = create_lsl_outlet(sn, "Marker", 1, 0.0, channel_format = 'int16')
    else:
        p_marker            = None
        faros_outlet_marker = None
 
    # (4) ----- RR -----
    if packet_size['n_rr_s'] > 0  and 'RR' in active_streams:
        p_rr              = get_data_packet(1, 'rr')
        sn                = 'faros_RR' if device_name is None else device_name+'_RR'
        faros_outlet_rr   = create_lsl_outlet(sn, "RR", 1, 0.0, channel_format = 'int16')
    else:
        p_rr              = None
        faros_outlet_rr   = None
        
    # (5) ----- Temperature -----
    if packet_size['n_temp_s'] > 0 and 'temp' in active_streams:
        p_temp            = get_data_packet(1, 'temp')
        sn                =  'faros_RR' if device_name is None else device_name+'_RR'
        faros_outlet_temp = create_lsl_outlet(sn, "Temp", 1, 5, channel_format = 'float32')
    else:
        p_temp            = None
        faros_outlet_temp = None

    streamer_thread = StreamerThread(stream_data   = False,
                                     faros_socket  = sock,
                                     packet_size   = packet_size,

                                     p_header      = p_header,
                                     p_ecg         = p_ecg,
                                     p_acc         = p_acc,
                                     p_marker      = p_marker,
                                     p_rr          = p_rr,
                                     p_temp        = p_temp,

                                     outlet_ecg    = faros_outlet_ecg,
                                     outlet_acc    = faros_outlet_acc,
                                     outlet_marker = faros_outlet_marker,
                                     outlet_rr     = faros_outlet_rr,
                                     outlet_temp   = faros_outlet_temp)

    # Start the streaming and show a UI
    return streamer_thread
    
    