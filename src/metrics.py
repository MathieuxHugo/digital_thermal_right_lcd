import subprocess
import re
import psutil
import time
import os
import json
import glob

try:
    import pyamdgpuinfo
except Exception as e:
    print("pyamdgpuinfo cannot start : ", str(e))

# --- FUNÇÕES AUXILIARES GLOBAIS ---

def get_cpu_temp_psutils():
    try:
        if hasattr(psutil, 'sensors_temperatures'):
            temps = psutil.sensors_temperatures()
            if temps:
                # Busca por sensores comuns em CPUs modernas
                for key in ['zenpower', 'k10temp', 'coretemp', 'cpu_thermal']:
                    if key in temps and temps[key]:
                        return temps[key][0].current
    except Exception:
        return None

def get_cpu_temp_linux():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            return float(f.read().strip()) / 1000.0
    except Exception:
        return None

def get_cpu_temp_raspberry_pi():
    try:
        output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
        return float(re.search(r'temp=(\d+\.\d+)', output).group(1))
    except Exception:
        return None

def get_gpu_temp_nvidia():
    try:
        from pynvml import (nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex, 
                            nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU, nvmlShutdown)
        nvmlInit()
        handle = nvmlDeviceGetHandleByIndex(0)
        temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
        nvmlShutdown()
        return temp
    except:
        try:
            output = subprocess.check_output(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader']).decode()
            return float(output.strip().split('\n')[0])
        except:
            return None

def get_cpu_usage():
    return psutil.cpu_percent(interval=None)

def get_gpu_usage_nvidia_smi():
    try: 
        output = subprocess.check_output(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader']).decode().strip()
        return int(output.split()[0])
    except Exception:
        return None
    
def get_gpu_usage_nvml():
    try:
        from pynvml import (nvmlInit, nvmlShutdown, nvmlDeviceGetHandleByIndex, 
                            nvmlDeviceGetUtilizationRates)
        nvmlInit()
        handle = nvmlDeviceGetHandleByIndex(0)
        utilization = nvmlDeviceGetUtilizationRates(handle)
        nvmlShutdown()
        return int(utilization.gpu)
    except:
        return None

def get_cpu_speed_psutil():
    try:
        freq = psutil.cpu_freq()
        return int(freq.current) if freq and freq.current else None
    except Exception:
        return None

def get_cpu_speed_proc():
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'cpu MHz' in line.lower():
                    match = re.search(r'(\d+\.?\d*)', line)
                    return int(float(match.group(1))) if match else None
        return None
    except Exception:
        return None

def get_gpu_speed_nvml():
    try:
        from pynvml import (nvmlInit, nvmlShutdown, nvmlDeviceGetHandleByIndex, 
                            nvmlDeviceGetClockInfo, NVML_CLOCK_GRAPHICS)
        nvmlInit()
        handle = nvmlDeviceGetHandleByIndex(0)
        clock = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_GRAPHICS)
        nvmlShutdown()
        return int(clock)
    except:
        return None

def get_gpu_speed_nvidia_smi():
    try:
        output = subprocess.check_output(['nvidia-smi', '--query-gpu=clocks.current.graphics', '--format=csv,noheader']).decode().strip()
        match = re.search(r'(\d+)', output)
        return int(match.group(1)) if match else None
    except Exception:
        return None

# --- CLASSE METRICS ---

class Metrics:
    def __init__(self, update_interval=0.5):
        self.metrics_functions = {
            'cpu_temp': None, 'gpu_temp': None, 'cpu_usage': None,
            'gpu_usage': None, 'cpu_speed': None, 'gpu_speed': None,
            'cpu_watts': None, 'gpu_watts': None
        }
        self.metrics = {
            'cpu_temp': 0, 'gpu_temp': 0, 'cpu_usage': 0,
            'gpu_usage': 0, 'cpu_speed': 0, 'gpu_speed': 0,
            'cpu_watts': 0, 'gpu_watts': 0
        }
        
        # Carregar GPU vendor da config
        config_path = os.environ.get('DIGITAL_LCD_CONFIG', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json'))
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.gpu_vendor = config.get('gpu_vendor', 'nvidia')
        except:
            self.gpu_vendor = 'nvidia'

        # Inicialização AMD
        self.gpu = None
        if self.gpu_vendor == 'amd':
            try:
                if pyamdgpuinfo.detect_gpus() > 0:
                    self.gpu = pyamdgpuinfo.get_gpu(0)
            except Exception as e:
                print(f"Erro ao inicializar AMD GPU: {e}")

        # Mapeamento de candidatos
        candidates =  {
            'cpu_temp': [get_cpu_temp_psutils, get_cpu_temp_linux, get_cpu_temp_raspberry_pi],
            'gpu_temp': [get_gpu_temp_nvidia] if self.gpu_vendor == 'nvidia' else [self.get_gpu_temp_amdgpuinfo],
            'cpu_usage': [get_cpu_usage],
            'gpu_usage': [get_gpu_usage_nvml, get_gpu_usage_nvidia_smi] if self.gpu_vendor == 'nvidia' else [self.get_gpu_usage_amd],
            'cpu_speed': [get_cpu_speed_psutil, get_cpu_speed_proc],
            'gpu_speed': [get_gpu_speed_nvml, get_gpu_speed_nvidia_smi] if self.gpu_vendor == 'nvidia' else [self.get_gpu_speed_amd],
            
            # ATUALIZADO: Soma dos power inputs
            'cpu_watts': [self.get_cpu_power_zenpower_sum, self.get_cpu_power_linux, self.get_cpu_power_estimate],
            'gpu_watts': [self.get_gpu_power_nvidia] if self.gpu_vendor == 'nvidia' else [self.get_gpu_power_amd],
        }

        # Validação das funções
        for metric, functions in candidates.items():
            for function in functions:
                try:
                    result = function()
                    if result is not None:
                        self.metrics[metric] = int(result)
                        self.metrics_functions[metric] = function
                        break
                except Exception as e:
                    # print(f"Debug: Falha na função {function.__name__} para {metric}: {e}")
                    continue

        self.last_update = time.time()
        self.update_interval = update_interval

    def get_metrics(self, temp_unit):
        now = time.time()
        if now - self.last_update < self.update_interval:
            metrics = self.metrics.copy()
            metrics['updated'] = False
        else:
            for metric, function in self.metrics_functions.items():
                if function:
                    try:
                        result = function()
                        self.metrics[metric] = int(result) if result is not None else 0
                    except:
                        self.metrics[metric] = 0
            self.last_update = now
            metrics = self.metrics.copy()
            metrics['updated'] = True

        for device in ["cpu", "gpu"]:
            if temp_unit.get(device) == "fahrenheit":
                metrics[f"{device}_temp"] = int(metrics[f"{device}_temp"] * 9 / 5 + 32)
        return metrics

    # --- MÉTODOS DE POWER E AMD ---

    def get_cpu_power_zenpower_sum(self):
        """Lê o consumo de energia (em Watts) do módulo zenpower e SOMA power1_input + power2_input"""
        try:
            # Procura por pastas hwmon
            base_dir = '/sys/class/hwmon'
            hwmon_dirs = glob.glob(os.path.join(base_dir, 'hwmon*'))
            
            for hwmon in hwmon_dirs:
                name_path = os.path.join(hwmon, 'name')
                if os.path.exists(name_path):
                    with open(name_path, 'r') as f:
                        name = f.read().strip()
                    
                    if name == 'zenpower':
                        total_watts = 0
                        
                        # Tenta ler power1_input (SVI2_P_Core)
                        power1_path = os.path.join(hwmon, 'power1_input')
                        if os.path.exists(power1_path):
                            with open(power1_path, 'r') as pf:
                                micros = int(pf.read().strip())
                                total_watts += micros / 1_000_000  # Converte uW para W
                        
                        # Tenta ler power2_input (SVI2_P_SoC)
                        power2_path = os.path.join(hwmon, 'power2_input')
                        if os.path.exists(power2_path):
                            with open(power2_path, 'r') as pf:
                                micros = int(pf.read().strip())
                                total_watts += micros / 1_000_000  # Converte uW para W
                        
                        # Retorna a soma total
                        return int(total_watts)
        except:
            return None
        return None

    def get_cpu_power_zenpower(self):
        """Lê o consumo de energia (em Watts) do módulo zenpower no Linux (apenas power1)"""
        try:
            # Procura por pastas hwmon
            base_dir = '/sys/class/hwmon'
            hwmon_dirs = glob.glob(os.path.join(base_dir, 'hwmon*'))
            
            for hwmon in hwmon_dirs:
                name_path = os.path.join(hwmon, 'name')
                if os.path.exists(name_path):
                    with open(name_path, 'r') as f:
                        name = f.read().strip()
                    
                    if name == 'zenpower':
                        # Zenpower normalmente expõe power1_input (SVI2_P_Core) em microwatts
                        power_path = os.path.join(hwmon, 'power1_input')
                        if os.path.exists(power_path):
                            with open(power_path, 'r') as pf:
                                micros = int(pf.read().strip())
                                return int(micros / 1_000_000) # Converte uW para W
        except:
            return None
        return None

    def get_cpu_power_linux(self):
        try:
            path = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
            with open(path, 'r') as f:
                curr_e = int(f.read().strip())
                curr_t = time.time()
                if hasattr(self, 'last_e'):
                    energy_diff = curr_e - self.last_e
                    time_diff = curr_t - self.last_t
                    watts = (energy_diff / 1_000_000) / time_diff
                    self.last_e, self.last_t = curr_e, curr_t
                    return max(0, int(watts))
                self.last_e, self.last_t = curr_e, curr_t
                return 0
        except: return None

    def get_cpu_power_estimate(self):
        try:
            # Estimativa simples: Idle(15W) + Load%(Max TDP aprox 105W)
            # Ajuste esses valores se quiser uma estimativa mais precisa na falta do zenpower
            return int(15 + (105 * (psutil.cpu_percent() / 100.0)))
        except: return None

    def get_gpu_power_nvidia(self):
        try:
            from pynvml import (nvmlInit, nvmlShutdown, 
                              nvmlDeviceGetHandleByIndex, nvmlDeviceGetPowerUsage)
            nvmlInit()
            handle = nvmlDeviceGetHandleByIndex(0)
            power = int(nvmlDeviceGetPowerUsage(handle) / 1000)
            nvmlShutdown()
            return power
        except: return None
    
    def get_gpu_power_amd(self):
        """Lê o consumo da GPU AMD usando pyamdgpuinfo"""
        try:
            if self.gpu:
                # query_power() retorna watts diretamente
                return int(self.gpu.query_power())
        except:
            return None
        return None

    def get_gpu_usage_amd(self):
        return int(self.gpu.query_load() * 100) if self.gpu else None

    def get_gpu_temp_amdgpuinfo(self):
        return self.gpu.query_temperature() if self.gpu else None

    def get_gpu_speed_amd(self):
        # query_sclk retorna Hz, dividimos por 1M para MHz
        return int(self.gpu.query_sclk() / 1_000_000) if self.gpu else None