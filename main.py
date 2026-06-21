import serial
import datetime
import argparse

VERSION = "0.0.0"

# Set expected data input format:
data_separator = ','
data_end = '\n'

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fail Safe Serial Data Logger')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument('port', type=str, help='Serial port (e.g. /dev/ttyUSB0 or COM3)')
    parser.add_argument('baudrate', type=int, help='Baud rate (e.g. 9600)')
    parser.add_argument('output', type=str, help='Output file path')
    parser.add_argument('--separator', type=str, default=data_separator, help='Data separator (default: ",")')
    parser.add_argument('--end', type=str, default=data_end, help='Data end character (default: "\\n")')
    args = parser.parse_args()

    ser = serial.Serial(args.port, args.baudrate, timeout=1)

    with open(args.output, 'w', newline='') as f:
        print(f"Logging to '{args.output}' on {args.port} at {args.baudrate} baud. Press Ctrl+C to stop.")
        try:
            while True:
                line = ser.readline().decode().strip()
                if line:
                    fields = line.split(data_separator)
                    timestamp = datetime.datetime.now().isoformat()
                    f.write(timestamp + data_separator + data_separator.join(fields) + data_end)
                    f.flush()
                    print(f"[{timestamp}] {fields}")

        except KeyboardInterrupt:
            print("[EXIT] Stopping data logging.")
            
        finally:
            ser.close()

