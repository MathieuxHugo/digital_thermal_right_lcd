import subprocess
import re
import psutil
import time

try:
    import pyamdgpuinfo
except Exception as e:
    print("pyamdgpuinfo cannot start : ",str(e))



class Metrics:
    def __init__(self, update_interval=0.5):
        self.metrics_functions = {
            'cpu_temp': None,
            'gpu_temp': None,
            'cpu_usage': None,
            'gpu_usage': None
        }
        self.metrics = {
            'cpu_temp': 0,
            'gpu_temp': 0,
            'cpu_usage': 0,
            'gpu_usage': 0
        }
        try:
            device_count = pyamdgpuinfo.detect_gpus()
            if device_count > 0:
                self.gpu = pyamdgpuinfo.get_gpu(0)
            else:
                print(f"No AMD GPU detected.")
                self.gpu = -1
        except:
            print("pyamdgpuinfo not installed. GPU temperature will not be available.")
            self.gpu = None

        candidates =  {
            'cpu_temp': [get_cpu_temp_psutils,get_cpu_temp_linux,get_cpu_temp_windows_wmi,get_cpu_temp_windows_wintmp,get_cpu_temp_raspberry_pi],
            'gpu_temp': [get_gpu_temp_nvidia,get_gpu_temp_wintemp, self.get_gpu_temp_amdgpuinfo],
            'cpu_usage': [get_cpu_usage],
            'gpu_usage': [get_gpu_usage_nvml,get_gpu_usage_nvidia_smi,self.get_gpu_usage_amd,]
        }
        for metric, functions in candidates.items():
            for function in functions:
                try:
                    result = function()
                    if result is not None:
                        self.metrics[metric] = int(result)
                        self.metrics_functions[metric] = function
                        break
                except Exception as e:
                    continue
            if self.metrics_functions[metric] is None:
                print(f"Warning: No suitable function found for {metric}.")
        self.last_update = time.time()
        self.update_interval = update_interval # seconds

    def get_metrics(self, temp_unit):
        if time.time() - self.last_update < self.update_interval:
            return self.metrics
        else:
            for metric, function in self.metrics_functions.items():
                if function is not None:
                    try:
                        result = function()
                        if result is None:
                            self.metrics[metric] = 0
                        else:
                            self.metrics[metric] = int(result)
                    except Exception as e:
                        print(f"Error getting {metric}: {e}")
            self.last_update = time.time()
        for device in ["cpu", "gpu"]:
            if temp_unit[device] == "fahrenheit":
                self.metrics[f"{device}_temp"] = int(self.metrics[f"{device}_temp"] * 9 / 5 + 32)
        return self.metrics

    def get_gpu_usage_amd(self):
        try:
            if self.gpu is None:
                return None
            else:
                return int(self.gpu.query_load()*100)
        except :
            return None
        
    def get_gpu_temp_amdgpuinfo(self):
        try:
            return self.gpu.query_temperature()
        except Exception as e:
            print(f"Error getting AMD GPU temperature: {e}")
            return None

def get_cpu_temp_psutils():
    try:
        if hasattr(psutil, 'sensors_temperatures'):
            temps = psutil.sensors_temperatures()
            if temps:
                # Check common temperature sources
                for key in ['coretemp', 'cpu_thermal', 'k10temp', 'acpitz']:
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
def get_cpu_temp_windows_wmi(): 
    try:
        import wmi
        w = wmi.WMI(namespace="root\\wmi")
        temperature_info = w.MSAcpi_ThermalZoneTemperature()[0]
        return (temperature_info.CurrentTemperature / 10.0) - 273.15
    except Exception:
        return None

def get_cpu_temp_windows_wintmp():
    try:
        import WinTmp
        return WinTmp.CPU_Temp()
    except Exception:
        return None
    
def get_cpu_temp_raspberry_pi():
    try:
        output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
        return float(re.search(r'temp=(\d+\.\d+)', output).group(1))
    except Exception:
        return None

def get_gpu_temp_nvidia():
    # Try NVIDIA GPU first
    try:
        # Try using pynvml library
        try:
            from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex, \
                            nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU, nvmlShutdown
            
            nvmlInit()
            device_count = nvmlDeviceGetCount()
            
            if device_count > 0:
                handle = nvmlDeviceGetHandleByIndex(0)
                temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                nvmlShutdown()
                return temp
            
            nvmlShutdown()
        except:
            # Try using nvidia-smi command
            output = subprocess.check_output(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader']).decode()
            return float(output.strip().split('\n')[0])
    except:
        return None

def get_gpu_temp_wintemp():
    try:
        import WinTmp
        return WinTmp.GPU_Temp()
    except Exception:
        return None

def get_cpu_usage():
    """Get CPU usage percentage."""
    try:
        return psutil.cpu_percent(interval=None)
    except:
        print("Warning: Could not retrieve CPU usage.")
        return None

def get_gpu_usage_nvidia_smi():
    try: 
        output = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=utilization.gpu',
                '--format=csv,noheader']
        ).decode().strip()
        return int(output.split()[0])
    except Exception:
        return None
    
def get_gpu_usage_nvml():
    try:
        # NVIDIA GPUs using pynvml
        from pynvml import (nvmlInit, nvmlShutdown,
                        nvmlDeviceGetHandleByIndex,
                        nvmlDeviceGetUtilizationRates)
        nvmlInit()
        try:
            handle = nvmlDeviceGetHandleByIndex(0)
            utilization = nvmlDeviceGetUtilizationRates(handle)
            return int(utilization.gpu)
        finally:
            nvmlShutdown()
    except:
        return None
