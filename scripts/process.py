import time
import csv
import argparse
import random

# Generate test output
# python process.py --input input1.csv --output output1.csv --max_delay 20


# Configure arguments
parser = argparse.ArgumentParser(description='Batch Processing Script')
parser.add_argument('--input', required=True, help='Input CSV file path')
parser.add_argument('--output', required=True, help='Output file path')
parser.add_argument('--max_delay', type=int, default=20, 
                   help='Maximum random delay in seconds (default: 20)')
args = parser.parse_args()

# Simulate initialization
print(f"[STARTING] Processing {args.input}")
time.sleep(1)  # Initial delay

# Read input data
with open(args.input, 'r') as f:
    reader = csv.reader(f)
    rows = [row for row in reader]

# Simulate processing work
delay = random.randint(1, args.max_delay)
print(f"[PROCESSING] Simulating work for {delay} seconds...")
time.sleep(delay)

# Convert all values to uppercase
processed_rows = []
for row in rows:
    processed_rows.append([cell.upper() for cell in row])

# Write output
with open(args.output, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(processed_rows)

# Generate random success/failure
#if random.random() < 0.2:  # 20% chance of failure
#    raise Exception("Simulated processing failure!")

print(f"[COMPLETED] Results saved to {args.output}")
