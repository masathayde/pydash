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
        # Usamos o tempo para cálculo de vazão, usando o método descrito no documento de especificação.
        self.timer = Timer.get_instance()
        self.request_time = self.timer.get_started_time()
        # Mantém-se uma lista das qualidades escolhidas durante a execução do programa.
        # Ela é utilizada no algoritmo de decisão.
        self.chosen_qi = [0]
        # Também é mantida uma lista de valores de vazão medidos em cada ponto de escolha, para uso no algoritmo.
        self.throughput = [0]

    def handle_xml_request(self, msg):
        self.send_down(msg)

    def handle_xml_response(self, msg):
        # getting qi list
        self.parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = self.parsed_mpd.get_qi()
        self.send_up(msg)

    def handle_segment_size_request(self, msg):
        # Salvamos o tempo no momento em que o pedido é enviado. Será usado para calcular a vazão na hora em que o pedido...
        # ... receber uma resposta.
        self.request_time = self.timer.get_current_time()
        # Chamada do algoritmo de decisão.
        qidx = self.bola_proto()
        msg.add_quality_id(self.qi[qidx])
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        # Cálculo de vazão usando a medida de tempo salva anteriormente, usando o método usado em outras partes do pyDash.
        if msg.found():
            measured_throughput = msg.get_bit_length() / (self.timer.get_current_time() - self.request_time)
            self.throughput.append(measured_throughput)
        self.send_up(msg)

    def initialize(self):
        pass

    def finalization(self):
        pass

    # Para uma descrição mais detalhada do funcionamento do algoritmo, consultar o relatório.
    def bola_proto(self):
        # Parâmetros de controle usados no algoritmo, V e gama.
        V = 0.93
        # Higher gamma = higher buffer safety threshold
        gamma = 10

        self.chosen_qi.append(0)
        # Resolvemos o problema de otimização descrito no relatório para escolher o índice de qualidade do próximo segmento.
        self.chosen_qi[-1] = self.find_best_qi(V, gamma) # Passo 1

        # Ajustamos o nível de qualidade levando em consideração a vazão medida antes.
        # Só fazemos isso se o nível escolhido para o segmento atual for maior que o escolhido para o segmento anterior.
        # Checar relatório para explicação dos passos.
        if(self.chosen_qi[-1] > self.chosen_qi[-2]): # Passo 2 
            prev_measured_bandwidth = self.throughput[-1] # Passo 3 - Começo
            m_line = 0
            for i, quality in enumerate(self.qi):
                if prev_measured_bandwidth < quality:
                    break
                m_line = i
            if m_line >= self.chosen_qi[-1]: # Passo 4
                m_line = self.chosen_qi[-1]
            elif m_line < self.chosen_qi[-2]: # Passo 5
                m_line = self.chosen_qi[-2]
            else: # Passo 6
                m_line += 1
            self.chosen_qi[-1] = m_line # Passo 7
        # Já que player.py não pede segmentos novos se o buffer estiver cheio, nosso algoritmo não
        # faz essa checagem.
        return self.chosen_qi[-1] # Passo 8
    
    # Entre os valores de qualidade possíveis, escolhemos aquele que maximiza o valor de rho na equação
    # descrita no relatório.
    def find_best_qi(self, V, gamma):
        best_qi = 0
        max_value = -inf
        current_buffer = 0
        # Usamos o whiteboard para pegar o nível de buffer atual.
        if ( len(self.whiteboard.get_playback_buffer_size() ) > 0):
            current_buffer = self.whiteboard.get_playback_buffer_size()[-1][1]

        # Testamos todas as qualidades disponíveis.
        for i, bitrate in enumerate(self.qi):
            numerator = V*(self.bola_utility_function(bitrate) + gamma) - current_buffer # A equação a ser maximizada.
            segment_size = bitrate
            value = numerator / segment_size
            if (value > max_value):
                max_value = value
                best_qi = i
        return best_qi

    # Função de utilidade que descreve a satisfação do usuário, de acordo com a qualidade do vídeo.
    # Escolheu-se a função logarítmica por apresentar rendimentos decrescentes à medida que a qualidade sobe.
    def bola_utility_function(self, bitrate):
        return log(bitrate/self.qi[0])

