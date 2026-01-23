import numpy as np
from metrics import Metrics
from config import leds_indexes, NUMBER_OF_LEDS, display_modes
from utils import interpolate_color, get_random_color
import hid
import time
import datetime 
import json
import os
import sys

digit_to_segments = {
    0: ['a', 'b', 'c', 'd', 'e', 'f'],
    1: ['b', 'c'],
    2: ['a', 'b', 'g', 'e', 'd'],
    3: ['a', 'b', 'g', 'c', 'd'],
    4: ['f', 'g', 'b', 'c'],
    5: ['a', 'f', 'g', 'c', 'd'],
    6: ['a', 'f', 'g', 'e', 'c', 'd'],
    7: ['a', 'b', 'c'],
    8: ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
    9: ['a', 'b', 'g', 'f', 'c', 'd'],
}

class Controller:
    def __init__(self, config_path=None):
        self.temp_unit = {"cpu": "celsius", "gpu": "celsius"}
        self.metrics = Metrics()
        self.VENDOR_ID = 0x0416   
        self.PRODUCT_ID = 0x8001 
        self.dev = self.get_device()
        self.leds = np.array([0] * NUMBER_OF_LEDS)
        self.leds_indexes = leds_indexes
        
        if config_path is None:
            self.config_path = os.environ.get('DIGITAL_LCD_CONFIG', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json'))
        else:
            self.config_path = config_path
            
        self.cpt = 0
        self.cycle_duration = 50
        self.display_mode = None
        self.metrics_updates = 0
        self.alternating_cycle_duration = 5
        self.showing_cpu = True
        self.colors = np.array(["000000"] * NUMBER_OF_LEDS)
        self.layout = self.load_layout()
        self.update()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None

    def load_layout(self):
        try:
            layout_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'layout.json')
            with open(layout_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading layout: {e}")
            return None

    def get_device(self):
        try:
            return hid.Device(self.VENDOR_ID, self.PRODUCT_ID)
        except Exception as e:
            print(f"Error initializing HID device: {e}")
            return None

    def send_packets(self):
        """
        Envia dados para o PS120 EVO corrigindo o cabeçalho (20 bytes)
        e atualizando o tamanho do buffer para evitar overflow no display.
        """
        
        # 1. Converter cores para lista de bytes na ordem BRG (Hardware nativo)
        all_led_bytes = []
        for i in range(NUMBER_OF_LEDS):
            if self.leds[i] == 0:
                all_led_bytes.extend([0, 0, 0])
            else:
                color = self.colors[i]
                # Hex string para int
                r = int(color[0:2], 16)
                g = int(color[2:4], 16)
                b = int(color[4:6], 16)
                # Ordem BRG (Blue, Red, Green)
                all_led_bytes.extend([b, r, g])

        # ------------------------------------------------------------------
        # PACKET 0: Inicialização (Report ID 0 + 64 bytes)
        # ------------------------------------------------------------------
        p0_payload = [0xda, 0xdb, 0xdc, 0xdd] + [0]*8 + [0x01, 0, 0, 0]
        # Preenche com zeros até completar 64 bytes
        p0_payload += [0] * (64 - len(p0_payload))
        self.dev.write(bytes([0] + p0_payload))
        time.sleep(0.01)

        # ------------------------------------------------------------------
        # PACKET 1: Header (20 bytes) + Dados
        # ------------------------------------------------------------------
        # Correção Crítica 1: Tamanho do header é 20 bytes (termina com 00)
        # Correção Crítica 2: Alterado 0x17,0x01 (279 bytes) para 0x59,0x01 (345 bytes)
        # Isso diz ao hardware para esperar 115 LEDs, evitando que o excesso invada o display.
        
        header = [
            0xda, 0xdb, 0xdc, 0xdd,  # Magic
            0, 0, 0, 0, 0, 0, 0, 0,  # Padding 8 bytes
            0x02, 0, 0, 0,           # Seq
            0x59, 0x01, 0, 0         # SIZE: 345 bytes (115 LEDs * 3)
        ]
        
        # Constrói o fluxo contínuo de dados: Header + Todos os LEDs
        full_stream = header + all_led_bytes
        
        # Divide em pacotes de 64 bytes (Payload USB HID)
        # O Packet 1 pega os primeiros 64 bytes desse fluxo (20 header + 44 dados)
        # Os pacotes seguintes pegam o resto sequencialmente.
        
        chunk_size = 64
        for i in range(0, len(full_stream), chunk_size):
            chunk = full_stream[i:i+chunk_size]
            
            # Se o último pedaço for menor que 64, preenche com zeros
            if len(chunk) < 64:
                chunk += [0] * (64 - len(chunk))
            
            # Envia com o Report ID 0 na frente
            self.dev.write(bytes([0] + chunk))

    def draw_number(self, number, num_digits, digits_mapping):
        """Draw a number using the digit mapping from layout.json"""
        number_str = f"{number:0{num_digits}d}"
        for i, digit_char in enumerate(number_str):
            if i < len(digits_mapping):
                digit = int(digit_char)
                segments_to_light = digit_to_segments[digit]
                digit_map = digits_mapping[i]['map']
                for segment_name in segments_to_light:
                    segment_index = digit_map[segment_name]
                    self.leds[segment_index] = 1

    def draw_usage_phantom_spirit(self, usage):
        """Draw usage % with special handling for 100s digit LED and leading zeros"""
        if usage < 0 or usage > 199:
            return
        
        # Liga o símbolo de "%"
        self.leds[self.layout['usage_percent_led']] = 1
        
        usage_2digit = usage % 100
        
        # Lógica para Unidades (Sempre desenha)
        if len(self.layout['usage_1s_digit']) > 0:
            self.draw_number(usage_2digit % 10, 1, self.layout['usage_1s_digit'])
        
        # Lógica para Dezenas
        if len(self.layout['usage_10s_digit']) > 0:
            # Se for >= 10, desenha normal. 
            # Se for 100, usage_2digit é 0, mas precisamos que o "0" do meio apareça.
            if usage >= 100:
                self.draw_number(0, 1, self.layout['usage_10s_digit'])
            elif usage_2digit >= 10:
                self.draw_number(usage_2digit // 10, 1, self.layout['usage_10s_digit'])
        
        # Lógica para a Centena (LED isolado "1")
        if usage >= 100:
            self.leds[self.layout['usage_100s_led']] = 1

    def draw_speed_phantom_spirit(self, speed):
        """Draw 4-digit speed in MHz, skipping leading zeros"""
        if speed < 0 or speed > 9999:
            return
        
        # Draw MHz LED
        if 'speed_mhz_led' in self.layout:
            self.leds[self.layout['speed_mhz_led']] = 1
        
        # Draw speed digits, skipping leading zeros
        if 'speed_digits' in self.layout and len(self.layout['speed_digits']) >= 4:
            # Draw 1s digit (always)
            self.draw_number(speed % 10, 1, [self.layout['speed_digits'][0]])
            
            # Draw 10s digit if speed >= 10
            if speed >= 10:
                self.draw_number((speed // 10) % 10, 1, [self.layout['speed_digits'][1]])
            
            # Draw 100s digit if speed >= 100
            if speed >= 100:
                self.draw_number((speed // 100) % 10, 1, [self.layout['speed_digits'][2]])
            
            # Draw 1000s digit if speed >= 1000
            if speed >= 1000:
                self.draw_number(speed // 1000, 1, [self.layout['speed_digits'][3]])

    def draw_watts_phantom_spirit(self, watts):
        """Draw watts with W symbol"""
        if watts < 0 or watts > 999:
            return
        
        # Símbolo W
        if 'watts_w_led' in self.layout:
            self.leds[self.layout['watts_w_led']] = 1
        
        hundreds = watts // 100
        tens = (watts // 10) % 10
        units = watts % 10
        
        # Centenas (apenas se >= 100)
        if watts >= 100 and len(self.layout.get('watts_digits', [])) > 0:
            self.draw_number(hundreds, 1, [self.layout['watts_digits'][0]])
        
        # Dezenas (apenas se >= 10)
        if watts >= 10 and len(self.layout.get('watts_digits', [])) > 1:
            self.draw_number(tens, 1, [self.layout['watts_digits'][1]])
        
        # Unidades (sempre)
        if len(self.layout.get('watts_digits', [])) > 2:
            self.draw_number(units, 1, [self.layout['watts_digits'][2]])

    def draw_temp_phantom_spirit(self, temp, device='cpu', unit='celsius'):
        """Draw temperature with CPU/GPU LED and unit"""
        if temp < 0 or temp > 999:
            return
        
        # CPU ou GPU LED
        if device == 'cpu':
            self.leds[self.layout['temp_cpu_led']] = 1
        else:
            self.leds[self.layout['temp_gpu_led']] = 1
        
        # Dígitos
        if len(self.layout['temp_1s_digit']) > 0:
            self.draw_number(temp % 10, 1, self.layout['temp_1s_digit'])
        
        if temp >= 10 and len(self.layout['temp_10s_digit']) > 0:
            self.draw_number((temp // 10) % 10, 1, self.layout['temp_10s_digit'])
        
        if temp >= 100 and len(self.layout['temp_100s_digit']) > 0:
            self.draw_number(temp // 100, 1, self.layout['temp_100s_digit'])
        
        # Unidade
        if unit == 'celsius':
            self.leds[self.layout['temp_celsius']] = 1
        else:
            self.leds[self.layout['temp_fahrenheit']] = 1

    def display_cpu_watts_mode(self):
        """Display CPU: Usage%, Speed (MHz), Watts, Temperature"""
        if not self.layout:
            return

        cpu_unit = self.config.get('cpu_temperature_unit', 'celsius')
        gpu_unit = self.config.get('gpu_temperature_unit', 'celsius')
        temp_unit = {'cpu': cpu_unit, 'gpu': gpu_unit}

        metrics = self.metrics.get_metrics(temp_unit=temp_unit)
        self.colors = self.get_config_colors(self.config, key=getattr(self, "color_mode", "usage"), metrics=metrics)

        cpu_usage = metrics.get("cpu_usage", 0)
        cpu_speed = metrics.get("cpu_speed", 0)
        cpu_watts = metrics.get("cpu_watts", 0)
        cpu_temp = metrics.get("cpu_temp", 0)

        self.draw_usage_phantom_spirit(cpu_usage)
        self.draw_speed_phantom_spirit(cpu_speed)
        self.draw_watts_phantom_spirit(cpu_watts)
        self.draw_temp_phantom_spirit(cpu_temp, device='cpu', unit=cpu_unit)

    def display_gpu_watts_mode(self):
        """Display GPU: Usage%, Speed (MHz), Watts, Temperature"""
        if not self.layout:
            return

        cpu_unit = self.config.get('cpu_temperature_unit', 'celsius')
        gpu_unit = self.config.get('gpu_temperature_unit', 'celsius')
        temp_unit = {'cpu': cpu_unit, 'gpu': gpu_unit}

        metrics = self.metrics.get_metrics(temp_unit=temp_unit)
        self.colors = self.get_config_colors(self.config, key=getattr(self, "color_mode", "usage"), metrics=metrics)

        gpu_usage = metrics.get("gpu_usage", 0)
        gpu_speed = metrics.get("gpu_speed", 0)
        gpu_watts = metrics.get("gpu_watts", 0)
        gpu_temp = metrics.get("gpu_temp", 0)

        self.draw_usage_phantom_spirit(gpu_usage)
        self.draw_speed_phantom_spirit(gpu_speed)
        self.draw_watts_phantom_spirit(gpu_watts)
        self.draw_temp_phantom_spirit(gpu_temp, device='gpu', unit=gpu_unit)

    def display_alternating_watts(self, metrics_updated):
        """Alterna entre CPU e GPU a cada cycle_duration segundos"""
        if not self.layout:
            return

        cpu_unit = self.config.get('cpu_temperature_unit', 'celsius')
        gpu_unit = self.config.get('gpu_temperature_unit', 'celsius')
        temp_unit = {'cpu': cpu_unit, 'gpu': gpu_unit}

        # Alterna apenas quando as métricas forem atualizadas
        if metrics_updated:
            self.metrics_updates += 1
            # Alterna quando atingir o cycle_duration (em segundos)
            if self.metrics_updates >= self.alternating_cycle_duration:
                self.metrics_updates = 0
                self.showing_cpu = not self.showing_cpu

        metrics = self.metrics.get_metrics(temp_unit=temp_unit)
        self.colors = self.get_config_colors(self.config, key=getattr(self, "color_mode", "usage"), metrics=metrics)
        
        if self.showing_cpu:
            # Mostra dados da CPU
            cpu_usage = metrics.get("cpu_usage", 0)
            cpu_speed = metrics.get("cpu_speed", 0)
            cpu_watts = metrics.get("cpu_watts", 0)
            cpu_temp = metrics.get("cpu_temp", 0)
            
            self.draw_usage_phantom_spirit(cpu_usage)
            self.draw_speed_phantom_spirit(cpu_speed)
            self.draw_watts_phantom_spirit(cpu_watts)
            self.draw_temp_phantom_spirit(cpu_temp, device='cpu', unit=cpu_unit)
        else:
            # Mostra dados da GPU
            gpu_usage = metrics.get("gpu_usage", 0)
            gpu_speed = metrics.get("gpu_speed", 0)
            gpu_watts = metrics.get("gpu_watts", 0)
            gpu_temp = metrics.get("gpu_temp", 0)
            
            self.draw_usage_phantom_spirit(gpu_usage)
            self.draw_speed_phantom_spirit(gpu_speed)
            self.draw_watts_phantom_spirit(gpu_watts)
            self.draw_temp_phantom_spirit(gpu_temp, device='gpu', unit=gpu_unit)

    def get_config_colors(self, config, key="usage", metrics=None):
        """CORRIGIDO: Pega cores do config"""
        conf_colors = config.get(key, {}).get('colors')

        if not conf_colors:
            conf_colors = ["000000"] * NUMBER_OF_LEDS
        elif len(conf_colors) != NUMBER_OF_LEDS:
            if key == "usage":
                base = conf_colors[0]
                conf_colors = [base] * NUMBER_OF_LEDS
            else:
                repeated = []
                while len(repeated) < NUMBER_OF_LEDS:
                    for c in conf_colors:
                        repeated.append(c)
                        if len(repeated) == NUMBER_OF_LEDS:
                            break
                conf_colors = repeated

        if metrics is None:
            metrics = self.metrics.get_metrics(self.temp_unit)
            
        colors = []
        for i, color in enumerate(conf_colors):
            if color.lower() == "random":
                colors.append(get_random_color())
            elif ";" in color:
                parts = color.split(';')
                metric = parts[0]
                stops = []
                for stop in parts[1:]:
                    stop_parts = stop.split(':')
                    stops.append({'color': stop_parts[0], 'value': int(stop_parts[1])})
                
                stops.sort(key=lambda x: x['value'])

                if metric == "usage":
                    usage_metric = "cpu_usage"
                    if getattr(self, "display_mode", "cpu_watts") in ["gpu_watts"]:
                        usage_metric = "gpu_usage"
                    elif getattr(self, "display_mode", "cpu_watts") == "alternating_watts":
                        if getattr(self, "showing_cpu", True):
                            usage_metric = "cpu_usage"
                        else:
                            usage_metric = "gpu_usage"

                    if usage_metric not in metrics:
                        colors.append(stops[0]['color'])
                        continue

                    metric_value = metrics[usage_metric]
                    chosen_color = stops[-1]['color']
                    for band in stops:
                        if metric_value < band['value']:
                            chosen_color = band['color']
                            break
                    colors.append(chosen_color)
                    continue

                if metric not in metrics:
                    colors.append(stops[0]['color'])
                    continue

                metric_value = metrics[metric]

                if metric_value <= stops[0]['value']:
                    colors.append(stops[0]['color'])
                    continue
                
                if metric_value >= stops[-1]['value']:
                    colors.append(stops[-1]['color'])
                    continue

                for j in range(len(stops) - 1):
                    if stops[j]['value'] <= metric_value < stops[j+1]['value']:
                        start_stop = stops[j]
                        end_stop = stops[j+1]
                        factor = (metric_value - start_stop['value']) / (end_stop['value'] - start_stop['value'])
                        colors.append(interpolate_color(start_stop['color'], end_stop['color'], factor))
                        break
            else:
                colors.append(color)
        return np.array(colors)
    
    def update(self):
        self.leds = np.array([0] * NUMBER_OF_LEDS)
        self.config = self.load_config()
        updated = False
        
        if self.config:
            VENDOR_ID = int(self.config.get('vendor_id', "0x0416"),16)
            PRODUCT_ID = int(self.config.get('product_id', "0x8001"),16)
            
            self.display_mode = self.config.get('display_mode', 'cpu_watts')
            self.color_mode = self.config.get('color_mode', 'usage')
                
            self.temp_unit = {device: self.config.get(f"{device}_temperature_unit", "celsius") for device in ["cpu", "gpu"]}
            metrics = self.metrics.get_metrics(temp_unit=self.temp_unit)
            updated = metrics['updated']
            
            self.update_interval = self.config.get('update_interval', 0.1)
            self.cycle_duration = int(self.config.get('cycle_duration', 5)/self.update_interval)
            
            # CORRIGIDO: alternating_cycle_duration deve ser o valor em SEGUNDOS da config
            self.alternating_cycle_duration = int(self.config.get('cycle_duration', 5))
            
            self.metrics.update_interval = self.config.get('metrics_update_interval', 0.5)
            self.leds_indexes = leds_indexes
            
            if self.display_mode not in display_modes:
                print(f"Warning: Display mode {self.display_mode} not compatible, switching to cpu_watts.")
                self.display_mode = "cpu_watts"
        else:
            VENDOR_ID = 0x0416
            PRODUCT_ID = 0x8001
            self.display_mode = 'cpu_watts'
            self.color_mode = 'usage'
            self.update_interval = 0.1
            self.cycle_duration = int(5/self.update_interval)
            self.alternating_cycle_duration = 5
            self.metrics.update_interval = 0.5
            self.leds_indexes = leds_indexes

        if VENDOR_ID != self.VENDOR_ID or PRODUCT_ID != self.PRODUCT_ID:
            self.VENDOR_ID = VENDOR_ID
            self.PRODUCT_ID = PRODUCT_ID
            self.dev = self.get_device()

        return updated

    def display(self):
        while True:
            self.config = self.load_config()
            metrics_updated = self.update()
            
            if self.dev is None:
                self.dev = self.get_device()
                time.sleep(1)
                continue

            if self.display_mode == "cpu_watts":
                self.display_cpu_watts_mode()
            elif self.display_mode == "gpu_watts":
                self.display_gpu_watts_mode()
            elif self.display_mode == "alternating_watts":
                self.display_alternating_watts(metrics_updated)
            elif self.display_mode == "debug_ui":
                self.colors = np.array(["00ff00"] * NUMBER_OF_LEDS)
                self.leds[:] = 1
            else:
                print(f"Unknown display mode: {self.display_mode}")

            self.send_packets()
            time.sleep(self.update_interval)


def main(config_path):
    controller = Controller(config_path=config_path)
    controller.display()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        print(f"Using config path: {config_path}")
    else:
        print("No config path provided, using default.")
        config_path = None
    main(config_path)