import numpy as np
from metrics import get_system_metrics
import hid
import time
import datetime 


NUMBER_OF_LEDS = 84
digit_mask = np.array(
    [
        [1, 1, 1, 0, 1, 1, 1],  # 0
        [0, 0, 1, 0, 0, 0, 1],  # 1
        [0, 1, 1, 1, 1, 1, 0],  # 2
        [0, 1, 1, 1, 0, 1, 1],  # 3
        [1, 0, 1, 1, 0, 0, 1],  # 4
        [1, 1, 0, 1, 0, 1, 1],  # 5
        [1, 1, 0, 1, 1, 1, 1],  # 6
        [0, 1, 1, 0, 0, 0, 1],  # 7
        [1, 1, 1, 1, 1, 1, 1],  # 8
        [1, 1, 1, 1, 0, 1, 1],  # 9
        [0, 0, 0, 0, 0, 0, 0],  # nothing
    ]
)

letter_mask = {
    'H': [1, 0, 1, 1, 1, 0, 1],
}



def _number_to_array(number):
    if number>=10:
        return _number_to_array(int(number/10))+[number%10]
    else:
        return [number]

def get_number_array(temp, array_length=3, fill_value=-1):
    if temp<0:
        return [fill_value]*array_length
    else:
        narray = _number_to_array(temp)
        if (len(narray)!=array_length):
            if(len(narray)<array_length):
                narray = np.concatenate([[fill_value]*(array_length-len(narray)),narray])
            else:
                narray = narray[1:]
        return narray

class Controller:
    def __init__(self):
        self.VENDOR_ID = 0x0416   
        self.PRODUCT_ID = 0x8001 
        self.HEADER = 'dadbdcdd000000000000000000000000fc00'
        self.UNKNOWN = '00ff'
        try:
            self.dev = hid.Device(self.VENDOR_ID, self.PRODUCT_ID)
        except Exception as e:
            print(f"Error initializing HID device: {e}")
            exit(1)
        self.leds = np.array([0] * NUMBER_OF_LEDS)
        self.leds_indexes = {
            "cpu_led": list(range(0, 2)),
            "cpu_temp": list(range(2, 23)),
            "cpu_celsius": 23,
            "cpu_fahrenheit": 24,
            "cpu_usage": list(range(25, 41)),
            "cpu_percent_led": 41,
            "gpu_led": [82, 83],
            "gpu_temp": list(range(81, 60, -1)),
            "gpu_celsius": 59,
            "gpu_fahrenheit": 60,
            "gpu_usage": list(range(58, 42, -1)),
            "gpu_percent_led": 42,
        }
        self.update()

    def set_leds(self, key, value):
        self.leds[self.leds_indexes[key]] = value

    def send_packets(self):
        message = "".join([self.colors[i][self.leds[i]] for i in range(NUMBER_OF_LEDS)])
        packet0 = bytes.fromhex(self.HEADER+self.UNKNOWN+message[:88])
        self.dev.write(packet0)
        packets = message[88:]
        for i in range(0,4):
            packet = bytes.fromhex('00'+packets[i*128:(i+1)*128])
            self.dev.write(packet)

    def set_temp(self, temperature : int, device='cpu', unit="celsius"):
        if temperature<1000:
            self.set_leds(device+'_temp', digit_mask[get_number_array(temperature)].flatten())
            self.set_leds(device+'_'+unit, 1)
        else:
            raise Exception("The numbers displayed on the temperature LCD must be less than 1000")
    def set_usage(self, usage : int, device='cpu'):
        if usage<200:
            self.set_leds(device+'_usage', np.concatenate(([int(usage>=100)]*2,digit_mask[get_number_array(usage, array_length=2)].flatten())))
            self.set_leds(device+'_percent_led', 1)
        else:
            raise Exception("The numbers displayed on the usage LCD must be less than 200")

    def display_metrics(self, devices=["cpu","gpu"]):
        metrics = get_system_metrics()
        for device in devices:
            self.set_leds(device+"_led", 1)
            self.set_temp(metrics[device+"_temp"], device=device)
            self.set_usage(metrics[device+"_usage"], device=device)

    def display_time(self, device="cpu"):
        current_time = datetime.datetime.now()
        self.set_leds(device+'_temp', np.concatenate((digit_mask[get_number_array(current_time.hour, array_length=2, fill_value=0)].flatten(),letter_mask["H"])))
        self.set_leds(device+'_usage', np.concatenate(([0,0],digit_mask[get_number_array(current_time.minute, array_length=2, fill_value=0)].flatten())))



    def update(self):
        self.leds = np.array([0] * NUMBER_OF_LEDS)
        self.colors = np.array([["000000", "ffe000"]] * NUMBER_OF_LEDS)

def main():
    cpt = 0
    CYCLE_DURATION = 5
    controller = Controller()
    while(True):
        controller.update() 
        if cpt<CYCLE_DURATION/2:
            controller.display_time()
            controller.display_metrics(devices=['gpu'])
        else:
            controller.display_time(device="gpu")
            controller.display_metrics(devices=['cpu'])
        cpt=(cpt+1)%CYCLE_DURATION
        controller.send_packets()
        time.sleep(1)


if __name__ == '__main__':
    main()
