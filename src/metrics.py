import subprocess
import re
import psutil
import time
import os

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
            'gpu_usage': None,
            'cpu_frequency': None,
            'gpu_frequency': None,
            'cpu_power': None,
            'gpu_power': None,
        }
        self.metrics = {
            'cpu_temp': 0,
            'gpu_temp': 0,
            'cpu_usage': 0,
            'gpu_usage': 0,
            'cpu_frequency': 0,
            'gpu_frequency': 0,
            'cpu_power': 0,
            'gpu_power': 0,
        }
        try:
            device_count = pyamdgpuinfo.detect_gpus()
            if device_count > 0:
                self.gpu = pyamdgpuinfo.get_gpu(0)
            else:
                print("No AMD GPU detected.")
                self.gpu = -1
        except Exception:
            print("pyamdgpuinfo not installed. GPU temperature will not be available.")
            self.gpu = None

        candidates =  {
            'cpu_temp': [get_cpu_temp_psutils,get_cpu_temp_linux,get_cpu_temp_windows_wmi,get_cpu_temp_windows_wintmp,get_cpu_temp_raspberry_pi],
            'gpu_temp': [get_gpu_temp_nvidia,get_gpu_temp_wintemp, self.get_gpu_temp_amdgpuinfo],
            'cpu_usage': [get_cpu_usage],
            'gpu_usage': [get_gpu_usage_nvml,get_gpu_usage_nvidia_smi,self.get_gpu_usage_amd,],
            'cpu_frequency': [get_cpu_frequency_psutil, get_cpu_frequency_proc],
            'gpu_frequency': [get_gpu_frequency_nvml, get_gpu_frequency_nvidia_smi, get_gpu_frequency_nvidia_smi_alt, self.get_gpu_frequency_amdgpuinfo],
            # try multiple strategies for CPU power: sysfs scanning, RAPL, turbostat
            'cpu_power': [get_cpu_power_rapl, get_cpu_power_turbostat],
            'gpu_power': [get_gpu_power_nvml, get_gpu_power_nvidia_smi, self.get_gpu_power_amdgpuinfo],
        }
        for metric, functions in candidates.items():
            for function in functions:
                try:
                    result = function()
                    if result is not None:
                        self.metrics[metric] = int(result)
                        self.metrics_functions[metric] = function
                        break
                except Exception:
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
        except Exception:
            return None
        
    def get_gpu_temp_amdgpuinfo(self):
        try:
            return self.gpu.query_temperature()
        except Exception as e:
            print(f"Error getting AMD GPU temperature: {e}")
            return None

    def get_gpu_frequency_amdgpuinfo(self):
        try:
            # try common method names on pyamdgpuinfo GPU object
            if self.gpu is None:
                return None
            for method in ('query_sclk','query_mclk'):
                if hasattr(self.gpu, method):
                    try:
                        return int(getattr(self.gpu, method)()/10**6)
                    except Exception:
                        continue
            # fallback: some versions provide a `query_clock` with a name
            if hasattr(self.gpu, 'query_clock'):
                try:
                    return int(self.gpu.query_clock()/10**6)
                except Exception:
                    pass
            return None
        except Exception as e:
            print(f"Error getting AMD GPU frequency: {e}")
            return None

    def get_gpu_power_amdgpuinfo(self):
        try:
            if self.gpu is None:
                return None
            for method in ('query_power','query_power_draw','query_power_watt'):
                if hasattr(self.gpu, method):
                    try:
                        return int(getattr(self.gpu, method)())
                    except Exception:
                        continue
            return None
        except Exception as e:
            print(f"Error getting AMD GPU power: {e}")
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
        except Exception:
            # Try using nvidia-smi command
            output = subprocess.check_output(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader']).decode()
            return float(output.strip().split('\n')[0])
    except Exception:
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
    except Exception:
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
    except Exception:
        return None

# New helper functions for frequency and power

def get_cpu_frequency_psutil():
    try:
        f = psutil.cpu_freq()
        if f and f.current:
            return int(f.current)
    except Exception:
        return None

def get_cpu_frequency_proc():
    try:
        # Fallback to reading /proc/cpuinfo first "cpu MHz" entry
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'cpu MHz' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        return int(float(parts[1].strip()))
    except Exception:
        return None


def get_gpu_frequency_nvml():
    try:
        from pynvml import (nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetClockInfo, nvmlShutdown, NVML_CLOCK_GRAPHICS)
        nvmlInit()
        try:
            handle = nvmlDeviceGetHandleByIndex(0)
            clk = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_GRAPHICS)
            return int(clk/10**6)
        finally:
            nvmlShutdown()
    except Exception:
        return None


def get_gpu_frequency_nvidia_smi():
    try:
        output = subprocess.check_output(['nvidia-smi', '--query-gpu=clocks.gr', '--format=csv,noheader']).decode().strip()
        # might return lines like "1500 MHz" or just numeric
        val = output.split('\n')[0].strip()
        return int(re.sub(r'[^0-9]', '', val))
    except Exception:
        return None


def get_gpu_frequency_nvidia_smi_alt():
    """Alternative NVIDIA GPU frequency retrieval.
    Tries nvidia-smi with clocks.current.graphics (no units), then falls back to nvidia-settings query.
    Returns MHz as int or None.
    """
    try:
        # Try a newer/query field that may return numeric value without units
        output = subprocess.check_output([
            'nvidia-smi',
            '--query-gpu=clocks.current.graphics',
            '--format=csv,noheader,nounits'
        ], stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        if output:
            val = output.split('\n')[0].strip()
            return int(float(re.sub(r'[^0-9\.]', '', val)))
    except Exception:
        pass

    try:
        # Fallback to nvidia-settings (if available). Use -t for terse/raw output when supported.
        out = subprocess.check_output(['nvidia-settings', '-q', 'GPUCoreClock', '-t'], stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        # grab the first integer found
        m = re.search(r"(\d+)", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass

    return None

def get_cpu_power_rapl():
    try:
        # Try reading intel-rapl energy_uj counters and compute instantaneous power
        base = '/sys/class/powercap'
        import glob
        rapl_dirs = glob.glob(base + '/intel-rapl:*')
        if not rapl_dirs:
            return None
        # pick first package
        energy_file = None
        for d in rapl_dirs:
            cand = d + '/intel-rapl:0/energy_uj'
            if os.path.exists(cand):
                energy_file = cand
                break
        if energy_file is None:
            # try package-0 path
            for d in rapl_dirs:
                cand = d + '/energy_uj'
                if os.path.exists(cand):
                    energy_file = cand
                    break
        if energy_file is None:
            return None
        # sample energy over short interval
        with open(energy_file, 'r') as f:
            e1 = int(f.read().strip())
        import time
        time.sleep(0.1)
        with open(energy_file, 'r') as f:
            e2 = int(f.read().strip())
        # energy in microjoules over dt seconds => watts = (e2-e1)/1e6/dt
        dt = 0.1
        watt = (e2 - e1) / 1e6 / dt
        return int(abs(watt))
    except Exception:
        return None


def get_cpu_power_turbostat():
    """Try retrieving package power using turbostat command (may require root). Parse a 'PkgWatt' or similar entry.
    Returns watts as int or None.
    """
    try:
        out = subprocess.check_output(['turbostat', '--Summary'], stderr=subprocess.DEVNULL, timeout=2).decode()
        # Look for a line containing 'Package' or 'PkgWatt' with a number
        for line in out.splitlines():
            m = re.search(r'(?:Package|PkgWatt|PkgW)\D*(\d+(?:\.\d+)?)', line, re.IGNORECASE)
            if m:
                return int(float(m.group(1)))
        # Some turbostat variants print a header then a summary line; try to find a numeric column
        nums = re.findall(r'\d+\.?\d*', out)
        if nums:
            return int(float(nums[-1]))
    except Exception:
        return None
    return None


def get_gpu_power_nvml():
    try:
        from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetPowerUsage, nvmlShutdown
        nvmlInit()
        try:
            handle = nvmlDeviceGetHandleByIndex(0)
            # returns milliwatts
            mw = nvmlDeviceGetPowerUsage(handle)
            return int(mw / 1000)
        finally:
            nvmlShutdown()
    except Exception:
        return None


def get_gpu_power_nvidia_smi():
    try:
        output = subprocess.check_output(['nvidia-smi', '--query-gpu=power.draw', '--format=csv,noheader']).decode().strip()
        val = output.split('\n')[0].strip()
        return int(float(re.sub(r'[^0-9\.]', '', val)))
    except Exception:
        return None
