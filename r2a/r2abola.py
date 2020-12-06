# -*- coding: utf-8 -*-
"""
@author: Marco Antônio Athayde

@description: PyDash Project

Implementation of a buffer-based quality selection algorithm based on BOLA by Spiteri, Urgaonkar and Sitaraman.
Algorithm assumes segment size is 1 second.
"""

from player.parser import *
from r2a.ir2a import IR2A
from math import log
from math import inf
from base.timer import Timer

class R2ABola(IR2A):

    def __init__(self, id):
        IR2A.__init__(self, id)
        self.parsed_mpd = ''
        self.qi = []

        self.timer = Timer.get_instance()
        self.request_time = self.timer.get_started_time()
        self.chosen_qi = [0]
        self.throughput = [0]

    def handle_xml_request(self, msg):
        self.send_down(msg)

    def handle_xml_response(self, msg):
        # getting qi list
        self.parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = self.parsed_mpd.get_qi()
        self.send_up(msg)

    def handle_segment_size_request(self, msg):
        # time to define the segment quality choose to make the request
        self.request_time = self.timer.get_current_time()
        qidx = self.bola_proto()
        msg.add_quality_id(self.qi[qidx])
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        if msg.found():
            measured_throughput = msg.get_bit_length() / (self.timer.get_current_time() - self.request_time)
            self.throughput.append(measured_throughput)
        self.send_up(msg)

    def initialize(self):
        pass

    def finalization(self):
        pass

    def bola_proto(self):
        V = 0.93
        # Higher gamma = higher buffer safety threshold
        gamma = 10

        self.chosen_qi.append(0)
        self.chosen_qi[-1] = self.find_best_qi(V, gamma)

        if(self.chosen_qi[-1] > self.chosen_qi[-2]):
            prev_measured_bandwidth = self.throughput[-1]
            m_line = 0
            for i, quality in enumerate(self.qi):
                if prev_measured_bandwidth < quality:
                    break
                m_line = i
            if m_line >= self.chosen_qi[-1]:
                m_line = self.chosen_qi[-1]
            elif m_line < self.chosen_qi[-2]:
                m_line = self.chosen_qi[-2]
            else:
                m_line += 1
            self.chosen_qi[-1] = m_line
        
        # Since player.py won't request a new segment if the buffer is full, we don't have to worry about..
        # checking it ourselves.
        return self.chosen_qi[-1]
    
    def find_best_qi(self, V, gamma):
        best_qi = 0
        max_value = -inf
        current_buffer = 0
        if ( len(self.whiteboard.get_playback_buffer_size() ) > 0):
            current_buffer = self.whiteboard.get_playback_buffer_size()[-1][1]

        for i, bitrate in enumerate(self.qi):
            numerator = V*(self.bola_utility_function(bitrate) + gamma) - current_buffer
            segment_size = bitrate
            value = numerator / segment_size
            if (value > max_value):
                max_value = value
                best_qi = i
        return best_qi

    def bola_utility_function(self, bitrate):
        return log(bitrate/self.qi[0])

